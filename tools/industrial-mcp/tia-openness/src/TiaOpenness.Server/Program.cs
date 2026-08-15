using System.ComponentModel;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using TiaOpenness.Models;

namespace TiaOpenness.Server;

public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        if (args.Length > 0 && string.Equals(args[0], "--cli", StringComparison.OrdinalIgnoreCase))
        {
            return RunCli(args.Skip(1).ToArray());
        }

        var builder = Host.CreateApplicationBuilder(args);

        builder.Logging.ClearProviders();
        // MCP stdio: never write protocol noise to stdout.
        builder.Logging.AddConsole(options =>
        {
            options.LogToStandardErrorThreshold = LogLevel.Trace;
        });

        var tiaVersion = Environment.GetEnvironmentVariable("TIA_VERSION") ?? TiaConnection.DefaultVersion;
        builder.Services.AddSingleton(new TiaConnection(tiaVersion));
        builder.Services.AddSingleton<ProjectService>();
        builder.Services.AddSingleton<BlockService>();
        builder.Services.AddSingleton<TiaOpennessTools>();

        builder.Services
            .AddMcpServer(options =>
            {
                options.ServerInfo = new()
                {
                    Name = "researchos-tia-openness",
                    Version = "0.1.0",
                };
            })
            .WithStdioServerTransport()
            .WithTools<TiaOpennessTools>();

        await builder.Build().RunAsync();
        return 0;
    }

    /// <summary>
    /// One-shot CLI for Python importer / CI (avoids holding an MCP stdio session).
    /// Examples:
    ///   TiaOpenness.Server.exe --cli status
    ///   TiaOpenness.Server.exe --cli export-project --project C:\p\x.ap19 --export-dir C:\out [--skip-compile]
    ///   TiaOpenness.Server.exe --cli import-block --project C:\p\x.ap19 --xml C:\b.xml
    /// </summary>
    private static int RunCli(string[] args)
    {
        if (args.Length == 0)
        {
            Console.Error.WriteLine(
                "Usage: --cli status | export-project --project <ap19> --export-dir <dir> [--plc name] [--version V19] [--skip-compile] [--full|--blocks-only] | " +
                "import-block --project <ap19> --xml <file> [--plc name] [--no-overwrite] [--version V19] | " +
                "archive-project --project <ap19> --out-dir <dir> [--name file.zap19] [--version V19]");
            return 2;
        }

        var command = args[0].ToLowerInvariant();
        var opts = ParseOpts(args.Skip(1).ToArray());
        var version = Environment.GetEnvironmentVariable("TIA_VERSION") ?? TiaConnection.DefaultVersion;
        if (opts.TryGetValue("version", out var versionOpt) && !string.IsNullOrWhiteSpace(versionOpt))
        {
            version = versionOpt;
        }

        using var connection = new TiaConnection(version);
        var projects = new ProjectService(connection);
        var blocks = new BlockService(projects);

        try
        {
            if (command == "status")
            {
                var status = connection.GetStatus();
                projects.ApplyStatus(status);
                Console.WriteLine(JsonSerializer.Serialize(status, JsonDefaults.Options));
                return status.OpennessGroupInToken && status.OpennessAvailable ? 0 : 1;
            }

            if (command == "export-project")
            {
                if (!opts.TryGetValue("project", out var project) || string.IsNullOrWhiteSpace(project))
                {
                    Console.Error.WriteLine("Missing --project");
                    return 2;
                }
                if (!opts.TryGetValue("export-dir", out var exportDir) || string.IsNullOrWhiteSpace(exportDir))
                {
                    Console.Error.WriteLine("Missing --export-dir");
                    return 2;
                }

                opts.TryGetValue("plc", out var plc);
                var skipCompile = IsTruthyFlag(opts, "skip-compile")
                    || IsTruthyEnv("TIA_EXPORT_SKIP_COMPILE");
                var blocksOnly = IsTruthyFlag(opts, "blocks-only")
                    || IsTruthyEnv("RESEARCHOS_TIA_EXPORT_BLOCKS_ONLY");
                var openSw = System.Diagnostics.Stopwatch.StartNew();
                var opened = projects.OpenProject(project, plc, withoutUi: true);
                openSw.Stop();
                if (!opened.Ok)
                {
                    Console.WriteLine(JsonSerializer.Serialize(opened, JsonDefaults.Options));
                    return 3;
                }

                var surface = new ExportSurface(projects, blocks);
                var exported = surface.Export(exportDir, skipCompile, blocksOnly);
                var payload = new
                {
                    ok = exported.Ok,
                    openMs = openSw.ElapsedMilliseconds,
                    project = opened,
                    export = exported,
                };
                Console.WriteLine(JsonSerializer.Serialize(payload, JsonDefaults.Options));
                return exported.Ok ? 0 : 4;
            }

            if (command == "import-block")
            {
                if (!opts.TryGetValue("project", out var project) || string.IsNullOrWhiteSpace(project))
                {
                    Console.Error.WriteLine("Missing --project");
                    return 2;
                }
                if (!opts.TryGetValue("xml", out var xml) || string.IsNullOrWhiteSpace(xml))
                {
                    Console.Error.WriteLine("Missing --xml");
                    return 2;
                }

                opts.TryGetValue("plc", out var plc);
                var overwrite = !opts.ContainsKey("no-overwrite");

                var opened = projects.OpenProject(project, plc, withoutUi: true);
                if (!opened.Ok)
                {
                    Console.WriteLine(JsonSerializer.Serialize(opened, JsonDefaults.Options));
                    return 3;
                }

                var imported = blocks.ImportBlock(xml, overwrite);
                if (!imported.Ok)
                {
                    var failPayload = new
                    {
                        ok = false,
                        project = opened,
                        import = imported,
                    };
                    Console.WriteLine(JsonSerializer.Serialize(failPayload, JsonDefaults.Options));
                    return 4;
                }

                var saved = projects.SaveProject();
                var importPayload = new
                {
                    ok = saved.Ok,
                    project = opened,
                    import = imported,
                    save = saved,
                };
                Console.WriteLine(JsonSerializer.Serialize(importPayload, JsonDefaults.Options));
                return saved.Ok ? 0 : 5;
            }

            if (command == "archive-project")
            {
                if (!opts.TryGetValue("project", out var project) || string.IsNullOrWhiteSpace(project))
                {
                    Console.Error.WriteLine("Missing --project");
                    return 2;
                }
                if (!opts.TryGetValue("out-dir", out var outDir) || string.IsNullOrWhiteSpace(outDir))
                {
                    Console.Error.WriteLine("Missing --out-dir");
                    return 2;
                }

                opts.TryGetValue("name", out var archiveName);
                opts.TryGetValue("plc", out var plc);

                var opened = projects.OpenProject(project, plc, withoutUi: true);
                if (!opened.Ok)
                {
                    Console.WriteLine(JsonSerializer.Serialize(opened, JsonDefaults.Options));
                    return 3;
                }

                var archived = projects.ArchiveProject(outDir, archiveName);
                var archivePayload = new
                {
                    ok = archived.Ok,
                    project = opened,
                    archive = archived,
                };
                Console.WriteLine(JsonSerializer.Serialize(archivePayload, JsonDefaults.Options));
                return archived.Ok ? 0 : 4;
            }

            Console.Error.WriteLine("Unknown CLI command: " + command);
            return 2;
        }
        finally
        {
            connection.Disconnect();
        }
    }

    private static Dictionary<string, string> ParseOpts(string[] args)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < args.Length; i++)
        {
            var a = args[i];
            if (!a.StartsWith("--", StringComparison.Ordinal)) continue;
            var key = a[2..];
            var value = "true";
            if (i + 1 < args.Length && !args[i + 1].StartsWith("--", StringComparison.Ordinal))
            {
                value = args[++i];
            }
            map[key] = value;
        }
        return map;
    }

    private static bool IsTruthyFlag(Dictionary<string, string> opts, string key)
    {
        if (!opts.TryGetValue(key, out var raw) || string.IsNullOrWhiteSpace(raw)) return false;
        return IsTruthy(raw);
    }

    private static bool IsTruthyEnv(string name)
    {
        var raw = Environment.GetEnvironmentVariable(name);
        return !string.IsNullOrWhiteSpace(raw) && IsTruthy(raw);
    }

    private static bool IsTruthy(string raw)
    {
        var v = raw.Trim();
        return v.Equals("1", StringComparison.OrdinalIgnoreCase)
            || v.Equals("true", StringComparison.OrdinalIgnoreCase)
            || v.Equals("yes", StringComparison.OrdinalIgnoreCase)
            || v.Equals("on", StringComparison.OrdinalIgnoreCase);
    }
}

[McpServerToolType]
public sealed class TiaOpennessTools
{
    private static readonly JsonSerializerOptions Json = JsonDefaults.Options;

    private readonly TiaConnection _connection;
    private readonly ProjectService _projects;
    private readonly BlockService _blocks;

    public TiaOpennessTools(TiaConnection connection, ProjectService projects, BlockService blocks)
    {
        _connection = connection;
        _projects = projects;
        _blocks = blocks;
    }

    [McpServerTool(Name = "tia.get_status"), Description(
        "Detect whether TIA Portal is running and whether Openness PublicAPI is available. " +
        "Also reports whether this MCP server currently holds a Portal/project connection.")]
    public string GetStatus()
    {
        var status = _connection.GetStatus();
        _projects.ApplyStatus(status);
        return JsonSerializer.Serialize(status, Json);
    }

    [McpServerTool(Name = "tia.open_project"), Description(
        "Open a Siemens TIA Portal project (.ap19 preferred for Milestone 1) via Openness. " +
        "Optionally select a PLC by device/software name.")]
    public string OpenProject(
        [Description("Absolute path to the TIA project file (.ap19 / .ap18 / .ap17 / .ap20).")] string project_path,
        [Description("Optional PLC device or software name. Empty = first PLC found.")] string? plc_name = null,
        [Description("Start Portal without UI when attach is unavailable (default true).")] bool without_ui = true)
    {
        var result = _projects.OpenProject(project_path, plc_name, without_ui);
        return JsonSerializer.Serialize(result, Json);
    }

    [McpServerTool(Name = "tia.list_blocks"), Description(
        "List PLC blocks from the open project. Types: OB, FB, FC, DB. " +
        "Requires a successful tia.open_project call first.")]
    public string ListBlocks(
        [Description("Optional type filter: OB | FB | FC | DB. Omit or * for all.")] string? type = null)
    {
        try
        {
            var result = _blocks.ListBlocks(type);
            return JsonSerializer.Serialize(result, Json);
        }
        catch (ArgumentException ex)
        {
            var fail = new ListBlocksResult
            {
                Ok = false,
                Error = new ToolError { Code = "invalid_argument", Message = ex.Message },
            };
            return JsonSerializer.Serialize(fail, Json);
        }
    }

    [McpServerTool(Name = "tia.export_block"), Description(
        "Export one PLC block to SimaticML XML via Openness Export(WithDefaults). " +
        "Downstream: XML → PLC Parser → PLC-IR → Neo4j → PLC Agent.")]
    public string ExportBlock(
        [Description("Block name, e.g. OB1, FB_Motor, FC10, DB_Data.")] string block_name,
        [Description("Output XML path. Default: %TEMP%/researchos-tia-export/<block>.xml")] string? export_path = null,
        [Description("Optional type hint OB|FB|FC|DB when names collide.")] string? type = null)
    {
        var result = _blocks.ExportBlock(block_name, export_path, type);
        return JsonSerializer.Serialize(result, Json);
    }

    [McpServerTool(Name = "tia.export_project"), Description(
        "Export the official Openness chapter-6 surface (PLC groups, hardware, HMI structure) " +
        "into export_dir (plc/<name>/..., hardware/, hmi/, manifest.json). " +
        "blocks_only=true keeps the legacy Blocks/ layout. Feed the directory to plc.tia.analyze / plc.tia.ingest.")]
    public string ExportProject(
        [Description("Output directory for SimaticML / AML XML (full layout or Blocks/).")] string export_dir,
        [Description("Skip ICompilable compile before export (default false).")] bool skip_compile = false,
        [Description("When true, only export OB/FB/FC/DB into Blocks/ (legacy). Default false = full official surface.")] bool blocks_only = false)
    {
        var surface = new ExportSurface(_projects, _blocks);
        var result = surface.Export(export_dir, skip_compile, blocks_only);
        return JsonSerializer.Serialize(result, Json);
    }

    [McpServerTool(Name = "tia.import_block"), Description(
        "Import a SimaticML block XML into the open project via Blocks.Import(FileInfo, ImportOptions). " +
        "Does not persist — call tia.save_project afterwards. overwrite=true uses ImportOptions.Override.")]
    public string ImportBlock(
        [Description("Absolute path to SimaticML block XML.")] string xml_path,
        [Description("When true, use ImportOptions.Override; when false, ImportOptions.None.")] bool overwrite = true)
    {
        var result = _blocks.ImportBlock(xml_path, overwrite);
        return JsonSerializer.Serialize(result, Json);
    }

    [McpServerTool(Name = "tia.save_project"), Description(
        "Save the currently open TIA project via Project.Save(). Call after tia.import_block.")]
    public string SaveProject()
    {
        var result = _projects.SaveProject();
        return JsonSerializer.Serialize(result, Json);
    }

    [McpServerTool(Name = "tia.archive_project"), Description(
        "Archive the open TIA project to a compressed .zap* file via Project.Archive(..., Compressed). " +
        "Use after import+save when the caller needs a downloadable Siemens archive.")]
    public string ArchiveProject(
        [Description("Target directory for the archive file.")] string out_dir,
        [Description("Archive file name, e.g. Line.zap19. Empty = derive from .apxx stem/version.")] string? name = null)
    {
        var result = _projects.ArchiveProject(out_dir, name);
        return JsonSerializer.Serialize(result, Json);
    }
}
