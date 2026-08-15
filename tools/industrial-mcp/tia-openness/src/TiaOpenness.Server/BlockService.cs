using System.Collections;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using TiaOpenness.Models;

namespace TiaOpenness.Server;

/// <summary>Lists and exports PLC blocks (OB / FB / FC / DB) via Openness.</summary>
public sealed class BlockService
{
    private static readonly HashSet<string> SupportedTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "OB", "FB", "FC", "DB",
    };

    private readonly ProjectService _projects;

    public BlockService(ProjectService projects)
    {
        _projects = projects;
    }

    public ListBlocksResult ListBlocks(string? typeFilter = null)
    {
        if (_projects.PlcSoftware is null)
        {
            return new ListBlocksResult
            {
                Ok = false,
                Error = new ToolError
                {
                    Code = "invalid_argument",
                    Message = "No project open. Call tia.open_project first.",
                },
            };
        }

        try
        {
            var filter = NormalizeTypeFilter(typeFilter);
            var blocks = new List<BlockInfo>();
            var blockGroup = GetProp(_projects.PlcSoftware, "BlockGroup")
                ?? throw new InvalidOperationException("PlcSoftware.BlockGroup is null.");

            CollectBlocks(blockGroup, relative: "", blocks);

            if (filter is not null)
            {
                blocks = blocks.Where(b => string.Equals(b.Type, filter, StringComparison.OrdinalIgnoreCase)).ToList();
            }

            var byType = blocks
                .GroupBy(b => b.Type)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase);

            return new ListBlocksResult
            {
                Ok = true,
                PlcName = _projects.PlcName,
                Count = blocks.Count,
                Blocks = blocks
                    .OrderBy(b => ExportRank(b.Type))
                    .ThenBy(b => b.Name, StringComparer.OrdinalIgnoreCase)
                    .ToList(),
                ByType = byType,
            };
        }
        catch (Exception ex)
        {
            return new ListBlocksResult
            {
                Ok = false,
                Error = new ToolError { Code = "openness_error", Message = Unwrap(ex).Message },
            };
        }
    }

    public ExportBlockResult ExportBlock(string blockName, string? exportPath = null, string? typeHint = null)
    {
        if (string.IsNullOrWhiteSpace(blockName))
        {
            return FailExport("invalid_argument", "block_name is required.");
        }

        if (_projects.PlcSoftware is null)
        {
            return FailExport("invalid_argument", "No project open. Call tia.open_project first.");
        }

        try
        {
            var blockGroup = GetProp(_projects.PlcSoftware, "BlockGroup")
                ?? throw new InvalidOperationException("PlcSoftware.BlockGroup is null.");

            var match = FindBlock(blockGroup, blockName.Trim(), typeHint, relative: "");
            if (match.Block is null)
            {
                return FailExport("not_found", $"Block '{blockName}' not found.");
            }

            var consistent = GetProp(match.Block, "IsConsistent");
            if (consistent is bool ok && !ok)
            {
                return FailExport(
                    "inconsistent_blocks",
                    $"Block '{blockName}' IsConsistent=false. Inconsistent blocks and PLC data types (UDT) cannot be exported. Compile the PLC software in TIA Portal, then retry.");
            }

            var outPath = string.IsNullOrWhiteSpace(exportPath)
                ? Path.Combine(Path.GetTempPath(), "researchos-tia-export", Sanitize(blockName) + ".xml")
                : Path.GetFullPath(exportPath);

            var dir = Path.GetDirectoryName(outPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            var exportOptionsType = match.Block.GetType().Assembly.GetType("Siemens.Engineering.ExportOptions")
                ?? throw new InvalidOperationException("ExportOptions type not found.");
            var withDefaults = Enum.Parse(exportOptionsType, "WithDefaults");

            var export = match.Block.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                    m.Name == "Export" &&
                    m.GetParameters().Length == 2);

            if (export is null)
            {
                return FailExport("dependency_unavailable", "Block.Export(FileInfo, ExportOptions) not found.");
            }

            var fileInfoType = export.GetParameters()[0].ParameterType;
            var fileInfo = Activator.CreateInstance(fileInfoType, outPath)!;
            export.Invoke(match.Block, new[] { fileInfo, withDefaults });

            return new ExportBlockResult
            {
                Ok = true,
                BlockName = match.Info!.Name,
                BlockType = match.Info.Type,
                ExportPath = outPath,
                Message = "Block exported as SimaticML XML.",
            };
        }
        catch (Exception ex)
        {
            var msg = Unwrap(ex).Message;
            var code = msg.IndexOf("Inconsistent", StringComparison.OrdinalIgnoreCase) >= 0
                ? "inconsistent_blocks"
                : "openness_error";
            return FailExport(code, msg);
        }
    }

    /// <summary>
    /// Import a SimaticML block XML via BlockGroup.Blocks.Import(FileInfo, ImportOptions).
    /// Does not save the project — call ProjectService.SaveProject afterwards.
    /// </summary>
    public ImportBlockResult ImportBlock(string xmlPath, bool overwrite = true)
    {
        if (string.IsNullOrWhiteSpace(xmlPath))
        {
            return FailImport("invalid_argument", "xml_path is required.");
        }

        if (_projects.PlcSoftware is null)
        {
            return FailImport("invalid_argument", "No project open. Call tia.open_project first.");
        }

        var full = Path.GetFullPath(xmlPath);
        if (!File.Exists(full))
        {
            return FailImport("not_found", $"XML file not found: {full}");
        }

        try
        {
            var blockGroup = GetProp(_projects.PlcSoftware, "BlockGroup")
                ?? throw new InvalidOperationException("PlcSoftware.BlockGroup is null.");
            var blocks = GetProp(blockGroup, "Blocks")
                ?? throw new InvalidOperationException("BlockGroup.Blocks is null.");

            var import = blocks.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                {
                    if (m.Name != "Import") return false;
                    var ps = m.GetParameters();
                    return ps.Length == 2 &&
                           ps[0].ParameterType.Name.IndexOf("FileInfo", StringComparison.Ordinal) >= 0 &&
                           ps[1].ParameterType.Name.IndexOf("ImportOptions", StringComparison.Ordinal) >= 0;
                });

            if (import is null)
            {
                return FailImport(
                    "dependency_unavailable",
                    "Blocks.Import(FileInfo, ImportOptions) not found.");
            }

            var fileInfoType = import.GetParameters()[0].ParameterType;
            var importOptionsType = import.GetParameters()[1].ParameterType;
            var optionName = overwrite ? "Override" : "None";
            object importOption;
            try
            {
                importOption = Enum.Parse(importOptionsType, optionName);
            }
            catch (ArgumentException)
            {
                // Some Openness builds use Overwrite instead of Override.
                if (overwrite)
                {
                    try
                    {
                        importOption = Enum.Parse(importOptionsType, "Overwrite");
                        optionName = "Overwrite";
                    }
                    catch (ArgumentException)
                    {
                        return FailImport(
                            "dependency_unavailable",
                            $"ImportOptions.{optionName} not found on Openness API.");
                    }
                }
                else
                {
                    return FailImport(
                        "dependency_unavailable",
                        $"ImportOptions.{optionName} not found on Openness API.");
                }
            }

            if (XmlLooksLikeSafety(full))
            {
                return FailImport(
                    "safety_block",
                    "Refusing Blocks.Import for Safety/F-block XML. Never write F-block bodies.");
            }

            var fileInfo = Activator.CreateInstance(fileInfoType, full)!;
            var imported = import.Invoke(blocks, new[] { fileInfo, importOption });
            var names = ExtractImportedNames(imported);
            if (names.Any(LooksLikeSafetyName))
            {
                return FailImport(
                    "safety_block",
                    "Refusing Blocks.Import: imported name looks like a Safety/F-block. Never write F-block bodies.");
            }

            return new ImportBlockResult
            {
                Ok = true,
                XmlPath = full,
                Overwrite = overwrite,
                ImportedNames = names,
                Message = names.Count == 0
                    ? $"Imported from {Path.GetFileName(full)} (ImportOptions.{optionName})."
                    : $"Imported {names.Count} item(s): {string.Join(", ", names)}.",
            };
        }
        catch (Exception ex)
        {
            return FailImport("openness_error", Unwrap(ex).Message);
        }
    }

    /// <summary>
    /// Import SCL via the official Openness External Source path:
    /// <c>PlcSoftware.ExternalSourceGroup.ExternalSources.CreateFromFile(name, path)</c>
    /// then <c>PlcExternalSource.GenerateBlocksFromSource()</c>.
    ///
    /// Verified against Siemens TIA Portal Openness docs
    /// ("Generating blocks from source" / "Adding external sources"):
    /// existing generated blocks are overwritten; an exception rolls the project back.
    /// Assumed (reflection, same pattern as Import): CreateFromFile(string, string),
    /// optional Find/Delete of a same-named external source, and a parameterless
    /// GenerateBlocksFromSource() (GenerateBlockOption.None if the overload exists).
    /// Does not save the project — call ProjectService.SaveProject afterwards.
    /// </summary>
    public GenerateFromSourceResult GenerateBlocksFromSource(string sclPath, bool overwrite = true)
    {
        if (string.IsNullOrWhiteSpace(sclPath))
        {
            return FailGenerate("invalid_argument", "scl_path is required.");
        }

        var full = Path.GetFullPath(sclPath);
        if (!File.Exists(full))
        {
            return FailGenerate("not_found", $"SCL file not found: {full}");
        }

        string sclText;
        try
        {
            sclText = File.ReadAllText(full);
        }
        catch (Exception ex)
        {
            return FailGenerate("openness_error", Unwrap(ex).Message);
        }

        if (SclLooksLikeSafety(sclText))
        {
            return FailGenerate(
                "safety_block",
                "Refusing GenerateBlocksFromSource for Safety/F-block SCL. Never write F-block bodies.");
        }

        if (_projects.PlcSoftware is null)
        {
            return FailGenerate("invalid_argument", "No project open. Call tia.open_project first.");
        }

        try
        {
            var extGroup = GetProp(_projects.PlcSoftware, "ExternalSourceGroup");
            if (extGroup is null)
            {
                return FailGenerate(
                    "dependency_unavailable",
                    "PlcSoftware.ExternalSourceGroup not found. Official Openness path is " +
                    "ExternalSourceGroup.ExternalSources.CreateFromFile + GenerateBlocksFromSource " +
                    "(Siemens TIA Portal Openness API, Generating blocks from source). " +
                    "This TIA/Openness build does not expose it. Linux Docker cannot import SCL.");
            }

            var sources = GetProp(extGroup, "ExternalSources");
            if (sources is null)
            {
                return FailGenerate(
                    "dependency_unavailable",
                    "ExternalSourceGroup.ExternalSources not found on this Openness build.");
            }

            var sourceName = Path.GetFileName(full);
            if (overwrite)
            {
                TryDeleteExternalSource(sources, sourceName);
            }

            var created = TryCreateExternalSource(sources, sourceName, full);
            if (created.Error is not null)
            {
                return created.Error;
            }

            var generated = InvokeGenerateBlocksFromSource(created.Source!);
            if (generated.Error is not null)
            {
                return generated.Error;
            }

            var names = generated.Names ?? new List<string>();
            if (names.Any(LooksLikeSafetyName))
            {
                return FailGenerate(
                    "safety_block",
                    "Refusing result: generated name looks like a Safety/F-block. Never write F-block bodies.");
            }

            return new GenerateFromSourceResult
            {
                Ok = true,
                SclPath = full,
                SourceName = sourceName,
                Overwrite = overwrite,
                GeneratedNames = names,
                Api = "ExternalSourceGroup.ExternalSources.CreateFromFile + GenerateBlocksFromSource",
                Message = names.Count == 0
                    ? $"Generated blocks from {sourceName} (GenerateBlocksFromSource)."
                    : $"Generated {names.Count} item(s) from {sourceName}: {string.Join(", ", names)}.",
            };
        }
        catch (Exception ex)
        {
            return FailGenerate("openness_error", Unwrap(ex).Message);
        }
    }

    /// <summary>Export all OB/FB/FC/DB blocks under exportDir/Blocks (and nested groups).</summary>
    public ExportBlockResult ExportAllBlocks(string exportDir, bool skipCompile = false)
    {
        if (_projects.PlcSoftware is null)
        {
            return FailExport("invalid_argument", "No project open. Call tia.open_project first.");
        }

        try
        {
            var root = Path.GetFullPath(exportDir);
            var blocksDir = Path.Combine(root, "Blocks");
            Directory.CreateDirectory(blocksDir);

            // Openness refuses inconsistent blocks; compile software first when the API allows
            // (unless caller opted out via --skip-compile).
            long compileMs = 0;
            string? compileNote;
            if (skipCompile)
            {
                compileNote = "Compile skipped by --skip-compile";
            }
            else
            {
                var compileSw = System.Diagnostics.Stopwatch.StartNew();
                compileNote = TryCompilePlcSoftware();
                compileSw.Stop();
                compileMs = compileSw.ElapsedMilliseconds;
            }

            var listSw = System.Diagnostics.Stopwatch.StartNew();
            var listed = ListBlocks();
            listSw.Stop();
            if (!listed.Ok)
            {
                return FailExport(listed.Error?.Code ?? "openness_error", listed.Error?.Message ?? "list failed");
            }

            var journalPath = Path.Combine(root, "_exported.jsonl");
            File.WriteAllText(journalPath, string.Empty, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

            var exportSw = System.Diagnostics.Stopwatch.StartNew();
            var exported = 0;
            var failures = new List<string>();
            var knowHowCount = listed.Blocks.Count(b => b.KnowHowProtected);
            // Serial Export on one Portal (COM/STA). Order OB → FB/FC → DB so Python
            // can start parsing program blocks while DBs are still exporting.
            var ordered = listed.Blocks
                .Where(info => info.Type is "OB" or "FB" or "FC" or "DB")
                .OrderBy(info => ExportRank(info.Type))
                .ThenBy(info => info.Name, StringComparer.OrdinalIgnoreCase)
                .ToList();
            foreach (var info in ordered)
            {
                var relative = string.IsNullOrWhiteSpace(info.Path)
                    ? info.Name
                    : info.Path!.Replace('/', Path.DirectorySeparatorChar);
                var target = Path.Combine(blocksDir, Sanitize(relative) + ".xml");
                var dir = Path.GetDirectoryName(target);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                var one = ExportBlock(info.Name, target, info.Type);
                if (one.Ok)
                {
                    exported++;
                    AppendExportJournal(journalPath, info, target, ok: true, error: null);
                }
                else
                {
                    var err = one.Error?.Message ?? "export failed";
                    failures.Add($"{info.Name}:{err}");
                    AppendExportJournal(journalPath, info, target, ok: false, error: err);
                }
            }
            exportSw.Stop();

            var inconsistent = failures.Any(f =>
                f.IndexOf("Inconsistent", StringComparison.OrdinalIgnoreCase) >= 0 ||
                f.IndexOf("IsConsistent=false", StringComparison.OrdinalIgnoreCase) >= 0);

            var message = failures.Count == 0
                ? $"Exported {exported} blocks to {root}"
                : $"Exported {exported} blocks; {failures.Count} failed (first: {failures[0]})";
            if (!string.IsNullOrWhiteSpace(compileNote))
            {
                message = compileNote + " | " + message;
            }
            message += $" | timings compile={compileMs}ms list={listSw.ElapsedMilliseconds}ms export={exportSw.ElapsedMilliseconds}ms knowHowProtected={knowHowCount}";

            return new ExportBlockResult
            {
                Ok = failures.Count == 0 || exported > 0,
                BlockName = "*",
                BlockType = "ALL",
                ExportPath = root,
                ExportedCount = exported,
                FailedCount = failures.Count,
                CompileMs = compileMs,
                ListMs = listSw.ElapsedMilliseconds,
                ExportMs = exportSw.ElapsedMilliseconds,
                KnowHowProtectedCount = knowHowCount,
                Message = message,
                Error = exported == 0
                    ? new ToolError
                    {
                        Code = failures.Any(f =>
                                   f.IndexOf("license", StringComparison.OrdinalIgnoreCase) >= 0)
                            ? "license_missing"
                            : inconsistent
                                ? "inconsistent_blocks"
                                : "export_failed",
                        Message = failures.FirstOrDefault() ?? "no blocks exported",
                    }
                    : null,
            };
        }
        catch (Exception ex)
        {
            return FailExport("openness_error", Unwrap(ex).Message);
        }
    }

    /// <summary>Public wrapper so full-surface export can compile before walking groups.</summary>
    public string CompilePlcSoftware() => TryCompilePlcSoftware();

    /// <summary>
    /// Fail-closed compile for writeback. If ICompilable is unreachable, Ok=false
    /// with code compile_api_unavailable — callers must not archive .zap.
    /// </summary>
    public CompilePlcResult CompilePlcSoftwareStrict()
    {
        if (_projects.PlcSoftware is null)
        {
            return new CompilePlcResult
            {
                Ok = false,
                ApiAvailable = false,
                Error = new ToolError
                {
                    Code = "invalid_argument",
                    Message = "No project open. Call tia.open_project first.",
                },
            };
        }

        try
        {
            var invoked = InvokeCompile(_projects.PlcSoftware);
            if (!invoked.ApiAvailable)
            {
                return new CompilePlcResult
                {
                    Ok = false,
                    ApiAvailable = false,
                    Message = invoked.Note,
                    Error = new ToolError
                    {
                        Code = "compile_api_unavailable",
                        Message = invoked.Note
                            + " Fail closed: do not archive .zap. Openness compile requires Windows HostGateway + TIA.",
                    },
                };
            }

            var errCount = ParseCount(invoked.ErrorCount);
            var warnCount = ParseCount(invoked.WarningCount);
            var state = invoked.State ?? "?";
            var failed = errCount is > 0
                || state.IndexOf("Error", StringComparison.OrdinalIgnoreCase) >= 0
                || state.IndexOf("Fail", StringComparison.OrdinalIgnoreCase) >= 0;
            var message = $"Compile State={state} errors={invoked.ErrorCount} warnings={invoked.WarningCount}";
            return new CompilePlcResult
            {
                Ok = !failed,
                ApiAvailable = true,
                State = state,
                ErrorCount = errCount,
                WarningCount = warnCount,
                InconsistentBlocks = invoked.Inconsistent,
                Message = message,
                Error = failed
                    ? new ToolError
                    {
                        Code = "compile_failed",
                        Message = message + (
                            invoked.Inconsistent.Count == 0
                                ? ""
                                : " inconsistent=" + string.Join(", ", invoked.Inconsistent)),
                    }
                    : null,
            };
        }
        catch (Exception ex)
        {
            return new CompilePlcResult
            {
                Ok = false,
                ApiAvailable = false,
                Error = new ToolError
                {
                    Code = "compile_api_unavailable",
                    Message = "Compile threw: " + Unwrap(ex).Message
                        + " Fail closed: do not archive .zap.",
                },
            };
        }
    }

    /// <summary>
    /// Best-effort PLC software compile via Openness ICompilable (reflection).
    /// Returns a short status note; never throws. Used on export only.
    /// </summary>
    private string TryCompilePlcSoftware()
    {
        if (_projects.PlcSoftware is null) return "Compile skipped: no PLC software.";
        try
        {
            var invoked = InvokeCompile(_projects.PlcSoftware);
            return invoked.Note;
        }
        catch (Exception ex)
        {
            return "Compile skipped: " + Unwrap(ex).Message;
        }
    }

    private readonly record struct CompileInvoke(
        bool ApiAvailable,
        string Note,
        string? State,
        string? ErrorCount,
        string? WarningCount,
        List<string> Inconsistent);

    private static CompileInvoke InvokeCompile(object plc)
    {
        MethodInfo? getService = null;
        foreach (var m in plc.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance))
        {
            if (m.Name == "GetService" && m.IsGenericMethodDefinition && m.GetParameters().Length == 0)
            {
                getService = m;
                break;
            }
        }
        if (getService is null)
        {
            return new CompileInvoke(false, "Compile skipped: GetService not found.", null, null, null, new());
        }

        Type? iCompilable = plc.GetType().Assembly.GetType("Siemens.Engineering.Compiler.ICompilable");
        if (iCompilable is null)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                iCompilable = asm.GetType("Siemens.Engineering.Compiler.ICompilable");
                if (iCompilable is not null) break;
            }
        }
        if (iCompilable is null)
        {
            return new CompileInvoke(false, "Compile skipped: ICompilable type not found.", null, null, null, new());
        }

        var service = getService.MakeGenericMethod(iCompilable).Invoke(plc, null);
        if (service is null)
        {
            return new CompileInvoke(false, "Compile skipped: ICompilable service null.", null, null, null, new());
        }

        var compile = service.GetType().GetMethod("Compile", Type.EmptyTypes);
        if (compile is null)
        {
            return new CompileInvoke(false, "Compile skipped: Compile() not found.", null, null, null, new());
        }

        var result = compile.Invoke(service, null);
        var state = GetProp(result, "State")?.ToString() ?? "?";
        var errCount = GetProp(result, "ErrorCount")?.ToString() ?? "?";
        var warnCount = GetProp(result, "WarningCount")?.ToString() ?? "?";
        var inconsistent = ExtractInconsistentNames(result);
        return new CompileInvoke(
            true,
            $"Compile State={state} errors={errCount} warnings={warnCount}",
            state,
            errCount,
            warnCount,
            inconsistent);
    }

    private void CollectBlocks(object group, string relative, List<BlockInfo> sink)
    {
        if (GetProp(group, "Blocks") is IEnumerable blocks)
        {
            foreach (var block in blocks)
            {
                sink.Add(ToBlockInfo(block, relative));
            }
        }

        if (GetProp(group, "Groups") is IEnumerable groups)
        {
            foreach (var child in groups)
            {
                var name = GetPropString(child, "Name") ?? "Group";
                var childRel = string.IsNullOrEmpty(relative) ? name : relative + "/" + name;
                CollectBlocks(child, childRel, sink);
            }
        }
    }

    private (object? Block, BlockInfo? Info) FindBlock(object group, string name, string? typeHint, string relative)
    {
        var hint = NormalizeTypeFilter(typeHint);

        if (GetProp(group, "Blocks") is IEnumerable blocks)
        {
            foreach (var block in blocks)
            {
                var info = ToBlockInfo(block, relative);
                if (!string.Equals(info.Name, name, StringComparison.OrdinalIgnoreCase)) continue;
                if (hint is not null && !string.Equals(info.Type, hint, StringComparison.OrdinalIgnoreCase)) continue;
                return (block, info);
            }
        }

        if (GetProp(group, "Groups") is IEnumerable groups)
        {
            foreach (var child in groups)
            {
                var childName = GetPropString(child, "Name") ?? "Group";
                var childRel = string.IsNullOrEmpty(relative) ? childName : relative + "/" + childName;
                var found = FindBlock(child, name, typeHint, childRel);
                if (found.Block is not null) return found;
            }
        }

        return (null, null);
    }

    private static BlockInfo ToBlockInfo(object block, string relative)
    {
        var name = GetPropString(block, "Name") ?? "Unknown";
        var typeName = block.GetType().Name;
        var mapped = MapBlockType(typeName, name);
        int? number = null;
        var numObj = GetProp(block, "Number");
        if (numObj is int i) number = i;
        else if (numObj is not null && int.TryParse(numObj.ToString(), out var parsed)) number = parsed;

        return new BlockInfo
        {
            Name = name,
            Type = mapped,
            Path = string.IsNullOrEmpty(relative) ? name : relative + "/" + name,
            ProgrammingLanguage = GetPropString(block, "ProgrammingLanguage"),
            Number = number,
            KnowHowProtected = IsKnowHowProtected(block),
        };
    }

    /// <summary>Export order: OB, then FB/FC, then DB. Serial Export stays on one Portal.</summary>
    public static int ExportRank(string type) => type switch
    {
        "OB" => 0,
        "FB" or "FC" => 1,
        "DB" => 2,
        _ => 3,
    };

    /// <summary>
    /// Best-effort KnowHow / know-how-protection flag via Openness reflection.
    /// Encrypted bodies still get exported (interface + CALLS); Python skips SCL only.
    /// </summary>
    public static bool IsKnowHowProtected(object block)
    {
        foreach (var name in new[] { "IsKnowHowProtected", "KnowHowProtection", "HasKnowHowProtection" })
        {
            var val = GetProp(block, name);
            if (val is null) continue;
            if (val is bool flag) return flag;
            var text = val.ToString() ?? "";
            if (text.Equals("True", StringComparison.OrdinalIgnoreCase)) return true;
            if (text.Equals("False", StringComparison.OrdinalIgnoreCase)) continue;
            if (text.IndexOf("Unprotected", StringComparison.OrdinalIgnoreCase) >= 0) continue;
            if (text.IndexOf("Protected", StringComparison.OrdinalIgnoreCase) >= 0) return true;
            foreach (var nested in new[] { "IsProtected", "Protected", "IsKnowHowProtected" })
            {
                var inner = GetProp(val, nested);
                if (inner is bool innerFlag && innerFlag) return true;
            }
        }
        return false;
    }

    private static void AppendExportJournal(string journalPath, BlockInfo info, string xmlPath, bool ok, string? error)
    {
        try
        {
            var line = JsonSerializer.Serialize(new
            {
                name = info.Name,
                type = info.Type,
                path = xmlPath,
                ok,
                knowHow = info.KnowHowProtected,
                error,
            });
            using var fs = new FileStream(
                journalPath,
                FileMode.Append,
                FileAccess.Write,
                FileShare.ReadWrite);
            using var writer = new StreamWriter(fs, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            writer.WriteLine(line);
            writer.Flush();
        }
        catch
        {
            // Journal is best-effort; Python still globs leftover XML after CLI exit.
        }
    }

    public static string MapBlockType(string clrTypeName, string blockName)
    {
        var t = clrTypeName ?? "";
        var upper = t.ToUpperInvariant();

        // net481: string.Contains(value, StringComparison) is unavailable — use IndexOf.
        if (ContainsIgnoreCase(t, "OrganizationBlock") ||
            upper == "OB" ||
            Regex.IsMatch(blockName ?? "", @"^OB\d+", RegexOptions.IgnoreCase))
        {
            return "OB";
        }

        if (ContainsIgnoreCase(t, "FunctionBlock") || upper == "FB")
        {
            return "FB";
        }

        if (upper == "FC" ||
            (ContainsIgnoreCase(t, "Function") && !ContainsIgnoreCase(t, "FunctionBlock")))
        {
            return "FC";
        }

        if (ContainsIgnoreCase(t, "DataBlock") ||
            ContainsIgnoreCase(t, "GlobalDB") ||
            ContainsIgnoreCase(t, "InstanceDB") ||
            ContainsIgnoreCase(t, "ArrayDB") ||
            upper is "DB" or "GLOBALDB" or "INSTANCEDB" or "ARRAYDB")
        {
            return "DB";
        }

        return "OTHER";
    }

    private static bool ContainsIgnoreCase(string haystack, string needle) =>
        haystack.IndexOf(needle, StringComparison.OrdinalIgnoreCase) >= 0;

    private static string? NormalizeTypeFilter(string? typeFilter)
    {
        if (string.IsNullOrWhiteSpace(typeFilter) || typeFilter!.Trim() == "*") return null;
        var t = typeFilter.Trim().ToUpperInvariant();
        if (!SupportedTypes.Contains(t))
        {
            throw new ArgumentException($"Unsupported block type '{typeFilter}'. Use OB, FB, FC, or DB.");
        }
        return t;
    }

    private static ExportBlockResult FailExport(string code, string message) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message },
    };

    private static ImportBlockResult FailImport(string code, string message) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message },
    };

    private static GenerateFromSourceResult FailGenerate(string code, string message) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message },
        Api = "ExternalSourceGroup.ExternalSources.CreateFromFile + GenerateBlocksFromSource",
    };

    /// <summary>F-OB / F-FB / F-FC / F-DB name heuristic (never write these bodies).</summary>
    public static bool LooksLikeSafetyName(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)) return false;
        var n = name.Trim();
        if (n.StartsWith("F-", StringComparison.OrdinalIgnoreCase)) return true;
        if (n.StartsWith("F_", StringComparison.OrdinalIgnoreCase)) return true;
        var upper = n.ToUpperInvariant();
        return upper.StartsWith("FOB") || upper.StartsWith("FFB")
            || upper.StartsWith("FFC") || upper.StartsWith("FDB");
    }

    /// <summary>F-LAD / F-FBD / F-SCL / F-STL language heuristic.</summary>
    public static bool LooksLikeSafetyLanguage(string? language)
    {
        if (string.IsNullOrWhiteSpace(language)) return false;
        var u = language.Trim().ToUpperInvariant();
        return u.StartsWith("F-") || u.StartsWith("F_") || u is "FSCL" or "FLAD" or "FFBD" or "FSTL";
    }

    /// <summary>Scan SCL header / keywords for Safety/F-block units.</summary>
    public static bool SclLooksLikeSafety(string? scl)
    {
        if (string.IsNullOrWhiteSpace(scl)) return false;
        if (Regex.IsMatch(scl, @"\bF-(?:FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK)\b", RegexOptions.IgnoreCase))
        {
            return true;
        }
        foreach (Match m in Regex.Matches(
            scl,
            @"(?:FUNCTION_BLOCK|FUNCTION|ORGANIZATION_BLOCK|DATA_BLOCK)\s+""([^""]+)""",
            RegexOptions.IgnoreCase))
        {
            if (LooksLikeSafetyName(m.Groups[1].Value)) return true;
        }
        return false;
    }

    /// <summary>Scan SimaticML XML for F-block name / F-language / failsafe markers.</summary>
    public static bool XmlLooksLikeSafety(string xmlPath)
    {
        try
        {
            var text = File.ReadAllText(xmlPath);
            if (Regex.IsMatch(text, @"<(?:ProgrammingLanguage)>\s*F[-_]", RegexOptions.IgnoreCase))
            {
                return true;
            }
            if (Regex.IsMatch(text, @"failsafe|f-runtime|safety\s+program", RegexOptions.IgnoreCase))
            {
                // Attribute noise is common; only treat as safety when a block name/lang also matches.
            }
            foreach (Match m in Regex.Matches(text, @"<Name>\s*([^<]+)\s*</Name>", RegexOptions.IgnoreCase))
            {
                if (LooksLikeSafetyName(m.Groups[1].Value.Trim())) return true;
            }
            return Regex.IsMatch(
                text,
                @"<(?:ProgrammingLanguage)>\s*(?:F-LAD|F-FBD|F-SCL|F-STL|FSCL|FLAD)\s*</",
                RegexOptions.IgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    private readonly record struct CreatedSource(object? Source, GenerateFromSourceResult? Error);
    private readonly record struct GeneratedBlocks(List<string>? Names, GenerateFromSourceResult? Error);

    private static void TryDeleteExternalSource(object sources, string sourceName)
    {
        try
        {
            var find = sources.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                    m.Name == "Find" &&
                    m.GetParameters().Length == 1 &&
                    m.GetParameters()[0].ParameterType == typeof(string));
            if (find is null) return;
            var existing = find.Invoke(sources, new object[] { sourceName });
            if (existing is null) return;
            var delete = existing.GetType().GetMethod("Delete", Type.EmptyTypes);
            delete?.Invoke(existing, null);
        }
        catch
        {
            // Overwrite is best-effort; CreateFromFile may still replace.
        }
    }

    private static CreatedSource TryCreateExternalSource(object sources, string sourceName, string fullPath)
    {
        var create = sources.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .FirstOrDefault(m =>
            {
                if (m.Name != "CreateFromFile") return false;
                var ps = m.GetParameters();
                return ps.Length == 2 && ps[0].ParameterType == typeof(string);
            });
        if (create is null)
        {
            return new CreatedSource(
                null,
                FailGenerate(
                    "dependency_unavailable",
                    "ExternalSources.CreateFromFile(string, path) not found. " +
                    "Official Openness API (Adding external sources) is unavailable on this build."));
        }

        var second = create.GetParameters()[1].ParameterType;
        object? secondArg = fullPath;
        if (second.Name.IndexOf("FileInfo", StringComparison.Ordinal) >= 0)
        {
            secondArg = Activator.CreateInstance(second, fullPath);
        }

        var source = create.Invoke(sources, new[] { sourceName, secondArg });
        if (source is null)
        {
            return new CreatedSource(
                null,
                FailGenerate("openness_error", "CreateFromFile returned null."));
        }
        return new CreatedSource(source, null);
    }

    private static GeneratedBlocks InvokeGenerateBlocksFromSource(object source)
    {
        var methods = source.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Where(m => m.Name == "GenerateBlocksFromSource")
            .ToList();
        if (methods.Count == 0)
        {
            return new GeneratedBlocks(
                null,
                FailGenerate(
                    "dependency_unavailable",
                    "PlcExternalSource.GenerateBlocksFromSource() not found. " +
                    "Official Openness API (Generating blocks from source) is unavailable on this build."));
        }

        var parameterless = methods.FirstOrDefault(m => m.GetParameters().Length == 0);
        object? generated;
        if (parameterless is not null)
        {
            generated = parameterless.Invoke(source, null);
        }
        else
        {
            var withOption = methods.FirstOrDefault(m => m.GetParameters().Length == 1);
            if (withOption is null)
            {
                return new GeneratedBlocks(
                    null,
                    FailGenerate(
                        "dependency_unavailable",
                        "GenerateBlocksFromSource overload not usable on this Openness build."));
            }
            var optType = withOption.GetParameters()[0].ParameterType;
            object? option = null;
            try
            {
                option = Enum.Parse(optType, "None");
            }
            catch (ArgumentException)
            {
                return new GeneratedBlocks(
                    null,
                    FailGenerate(
                        "dependency_unavailable",
                        "GenerateBlockOption.None not found on this Openness build."));
            }
            generated = withOption.Invoke(source, new[] { option });
        }

        return new GeneratedBlocks(ExtractImportedNames(generated), null);
    }

    private static int? ParseCount(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw) || raw == "?") return null;
        return int.TryParse(raw, out var n) ? n : null;
    }

    private static List<string> ExtractInconsistentNames(object? compileResult)
    {
        var names = new List<string>();
        if (compileResult is null) return names;
        var messages = GetProp(compileResult, "Messages") ?? GetProp(compileResult, "CompilerMessages");
        if (messages is not IEnumerable enumerable or string) return names;
        foreach (var item in enumerable)
        {
            if (item is null) continue;
            var path = GetPropString(item, "Path")
                ?? GetPropString(item, "Description")
                ?? GetPropString(item, "Message")
                ?? item.ToString();
            if (string.IsNullOrWhiteSpace(path)) continue;
            if (path!.IndexOf("Inconsistent", StringComparison.OrdinalIgnoreCase) < 0
                && path.IndexOf("error", StringComparison.OrdinalIgnoreCase) < 0)
            {
                continue;
            }
            names.Add(path);
            if (names.Count >= 32) break;
        }
        return names;
    }

    private static List<string> ExtractImportedNames(object? imported)
    {
        var names = new List<string>();
        if (imported is null) return names;

        if (imported is IEnumerable enumerable and not string)
        {
            foreach (var item in enumerable)
            {
                if (item is null) continue;
                // Import may return PlcBlock directly or a result wrapper with .Name / .ImportedObject.
                var name = GetPropString(item, "Name");
                if (string.IsNullOrWhiteSpace(name))
                {
                    var nested = GetProp(item, "ImportedObject") ?? GetProp(item, "Object");
                    name = GetPropString(nested, "Name");
                }
                if (!string.IsNullOrWhiteSpace(name)) names.Add(name!);
            }
            return names;
        }

        var single = GetPropString(imported, "Name");
        if (!string.IsNullOrWhiteSpace(single)) names.Add(single!);
        return names;
    }

    private static string Sanitize(string name) =>
        Regex.Replace(name, @"[\\/:*?""<>|]", "_");

    private static Exception Unwrap(Exception ex) =>
        ex is TargetInvocationException { InnerException: { } inner } ? inner : ex;

    private static object? GetProp(object? obj, string name) =>
        obj?.GetType().GetProperty(name)?.GetValue(obj);

    private static string? GetPropString(object? obj, string name) =>
        GetProp(obj, name)?.ToString();
}
