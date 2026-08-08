using System.Collections;
using System.Reflection;
using TiaOpenness.Models;

namespace TiaOpenness.Server;

/// <summary>Opens / tracks a TIA project and resolves PLC software.</summary>
public sealed class ProjectService
{
    private readonly TiaConnection _connection;
    private object? _project;
    private object? _plcSoftware;
    private string? _projectPath;
    private string? _projectName;
    private string? _plcName;
    private string? _deviceName;

    public ProjectService(TiaConnection connection)
    {
        _connection = connection;
    }

    public bool IsProjectOpen => _project is not null;
    public string? ProjectPath => _projectPath;
    public string? ProjectName => _projectName;
    public string? PlcName => _plcName;
    public string? DeviceName => _deviceName;
    public object? Project => _project;
    public object? PlcSoftware => _plcSoftware;

    public OpenProjectResult OpenProject(string projectPath, string? plcName = null, bool withoutUi = true)
    {
        if (string.IsNullOrWhiteSpace(projectPath))
        {
            return Fail("invalid_argument", "project_path is required.");
        }

        var full = Path.GetFullPath(projectPath);
        if (!File.Exists(full))
        {
            return Fail("not_found", $"Project file not found: {full}");
        }

        var ext = Path.GetExtension(full);
        if (!ext.StartsWith(".ap", StringComparison.OrdinalIgnoreCase))
        {
            return Fail("invalid_argument", $"Expected a TIA project (.ap19/.ap18/...), got: {ext}");
        }

        try
        {
            if (!TiaConnection.IsOpennessGroupInCurrentToken())
            {
                return Fail(
                    "openness_group_token_missing",
                    "Current logon token lacks 'Siemens TIA Openness'. Sign out/in after joining the group, then retry.");
            }

            // Prefer a dedicated WithoutUserInterface session for MCP open_project.
            // Attaching to an existing UI Portal often fails with Openness security checks.
            _connection.Connect(preferAttach: false, withoutUi: withoutUi);
            var portal = _connection.Portal
                ?? throw new InvalidOperationException("TIA Portal connection is not available.");

            var projectsProp = portal.GetType().GetProperty("Projects")
                ?? throw new MissingMemberException("TiaPortal.Projects");
            var projects = projectsProp.GetValue(portal)
                ?? throw new InvalidOperationException("TiaPortal.Projects is null.");

            var open = projects.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                    m.Name == "Open" &&
                    m.GetParameters().Length == 1 &&
                    m.GetParameters()[0].ParameterType.Name.Contains("FileInfo"));

            if (open is null)
            {
                // fallback: Open(string) / Open(FileInfo) any single-arg
                open = projects.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                    .FirstOrDefault(m => m.Name == "Open" && m.GetParameters().Length == 1);
            }

            if (open is null)
            {
                return Fail("dependency_unavailable", "Projects.Open method not found on Openness API.");
            }

            object arg = open.GetParameters()[0].ParameterType == typeof(string)
                ? full
                : Activator.CreateInstance(open.GetParameters()[0].ParameterType, full)!;

            _project = open.Invoke(projects, new[] { arg });
            _projectPath = full;
            _projectName = GetPropString(_project, "Name") ?? Path.GetFileNameWithoutExtension(full);

            var wanted = plcName?.Trim() ?? "";
            if (!TryResolvePlcSoftware(_project!, wanted, out _plcSoftware, out _deviceName, out _plcName))
            {
                return new OpenProjectResult
                {
                    Ok = false,
                    ProjectPath = full,
                    ProjectName = _projectName,
                    Error = new ToolError
                    {
                        Code = "not_found",
                        Message = string.IsNullOrEmpty(wanted)
                            ? "No PLC software found in project."
                            : $"No PLC software found matching '{wanted}'.",
                    },
                };
            }

            return new OpenProjectResult
            {
                Ok = true,
                ProjectPath = full,
                ProjectName = _projectName,
                PlcName = _plcName,
                DeviceName = _deviceName,
                Message = "Project opened via TIA Openness.",
            };
        }
        catch (TargetInvocationException ex)
        {
            var inner = ex.InnerException ?? ex;
            return Fail("openness_error", inner.Message, retryable: false);
        }
        catch (Exception ex)
        {
            return Fail("openness_error", ex.Message, retryable: false);
        }
    }

    public SaveProjectResult SaveProject()
    {
        if (_project is null)
        {
            return FailSave("invalid_argument", "No project open. Call tia.open_project first.");
        }

        try
        {
            var save = _project.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                    m.Name == "Save" &&
                    m.GetParameters().Length == 0);

            if (save is null)
            {
                return new SaveProjectResult
                {
                    Ok = false,
                    ProjectPath = _projectPath,
                    ProjectName = _projectName,
                    Error = new ToolError
                    {
                        Code = "dependency_unavailable",
                        Message = "Project.Save() not found on Openness API.",
                    },
                };
            }

            save.Invoke(_project, null);

            return new SaveProjectResult
            {
                Ok = true,
                ProjectPath = _projectPath,
                ProjectName = _projectName,
                Message = "Project saved.",
            };
        }
        catch (TargetInvocationException ex)
        {
            var inner = ex.InnerException ?? ex;
            return new SaveProjectResult
            {
                Ok = false,
                ProjectPath = _projectPath,
                ProjectName = _projectName,
                Error = new ToolError { Code = "openness_error", Message = inner.Message },
            };
        }
        catch (Exception ex)
        {
            return new SaveProjectResult
            {
                Ok = false,
                ProjectPath = _projectPath,
                ProjectName = _projectName,
                Error = new ToolError { Code = "openness_error", Message = ex.Message },
            };
        }
    }

    /// <summary>
    /// Archive the open project to a compressed .zap* via Project.Archive(DirectoryInfo, name, ProjectArchivationMode).
    /// </summary>
    public ArchiveProjectResult ArchiveProject(string targetDirectory, string? targetName = null)
    {
        if (_project is null)
        {
            return FailArchive("invalid_argument", "No project open. Call tia.open_project first.");
        }

        try
        {
            var dir = Path.GetFullPath(string.IsNullOrWhiteSpace(targetDirectory)
                ? Path.GetTempPath()
                : targetDirectory);
            Directory.CreateDirectory(dir);

            var name = string.IsNullOrWhiteSpace(targetName)
                ? InferZapName(_projectPath, _projectName)
                : Path.GetFileName(targetName);

            var archiveMethod = _project.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .FirstOrDefault(m =>
                    m.Name == "Archive" &&
                    m.GetParameters().Length == 3);

            if (archiveMethod is null)
            {
                return FailArchive(
                    "dependency_unavailable",
                    "Project.Archive(DirectoryInfo, string, ProjectArchivationMode) not found.");
            }

            var parms = archiveMethod.GetParameters();
            var dirInfoType = parms[0].ParameterType;
            var modeType = parms[2].ParameterType;
            object mode;
            try
            {
                mode = Enum.Parse(modeType, "Compressed");
            }
            catch
            {
                // Older enums may use different naming
                mode = Enum.GetValues(modeType).Cast<object>().First();
            }

            var dirInfo = Activator.CreateInstance(dirInfoType, dir)!;
            archiveMethod.Invoke(_project, new[] { dirInfo, name, mode });

            var archivePath = Path.Combine(dir, name);
            if (!File.Exists(archivePath))
            {
                // Openness may append extension; search for newest matching zap*
                var stem = Path.GetFileNameWithoutExtension(name);
                var candidates = Directory.GetFiles(dir, stem + "*")
                    .Concat(Directory.GetFiles(dir, "*.zap*"))
                    .Distinct()
                    .OrderByDescending(File.GetLastWriteTimeUtc)
                    .ToList();
                if (candidates.Count > 0)
                {
                    archivePath = candidates[0];
                }
            }

            return new ArchiveProjectResult
            {
                Ok = File.Exists(archivePath),
                ProjectPath = _projectPath,
                ArchivePath = archivePath,
                Message = File.Exists(archivePath)
                    ? $"Project archived to {archivePath}"
                    : "Archive completed but output file was not found.",
                Error = File.Exists(archivePath)
                    ? null
                    : new ToolError { Code = "archive_missing", Message = $"Expected archive under {dir}" },
            };
        }
        catch (TargetInvocationException ex)
        {
            var inner = ex.InnerException ?? ex;
            return FailArchive("openness_error", inner.Message);
        }
        catch (Exception ex)
        {
            return FailArchive("openness_error", ex.Message);
        }
    }

    private static string InferZapName(string? projectPath, string? projectName)
    {
        var stem = projectName;
        var ver = "19";
        if (!string.IsNullOrWhiteSpace(projectPath))
        {
            stem ??= Path.GetFileNameWithoutExtension(projectPath);
            var ext = Path.GetExtension(projectPath);
            if (ext.StartsWith(".ap", StringComparison.OrdinalIgnoreCase) && ext.Length > 3)
            {
                ver = ext[3..];
            }
        }
        stem ??= "project";
        return $"{stem}.zap{ver}";
    }

    public void ApplyStatus(TiaStatusResult status)
    {
        status.ProjectOpen = IsProjectOpen;
        status.ProjectPath = _projectPath;
        status.ProjectName = _projectName;
        status.Connected = _connection.IsConnected;
    }

    private bool TryResolvePlcSoftware(
        object project,
        string wantedName,
        out object? plcSoftware,
        out string? deviceName,
        out string? softwareName)
    {
        plcSoftware = null;
        deviceName = null;
        softwareName = null;

        var devicesProp = project.GetType().GetProperty("Devices");
        if (devicesProp?.GetValue(project) is not IEnumerable devices) return false;

        foreach (var device in devices)
        {
            var dName = GetPropString(device, "Name") ?? "";
            var itemsProp = device.GetType().GetProperty("DeviceItems");
            if (itemsProp?.GetValue(device) is not IEnumerable items) continue;

            foreach (var item in items)
            {
                var found = FindPlcSoftwareInItem(item, wantedName, dName);
                if (found is null) continue;
                plcSoftware = found;
                deviceName = dName;
                softwareName = GetPropString(found, "Name") ?? dName;
                return true;
            }
        }

        return false;
    }

    private object? FindPlcSoftwareInItem(object item, string wantedName, string deviceName)
    {
        foreach (var typeName in new[]
                 {
                     "Siemens.Engineering.HW.Features.SoftwareContainer",
                     "Siemens.Engineering.Software.SoftwareContainer",
                 })
        {
            var container = _connection.GetService(item, typeName);
            if (container is null) continue;
            var software = GetProp(container, "Software");
            if (software is null) continue;

            var isPlc = software.GetType().FullName?.Contains("PlcSoftware") == true
                        || software.GetType().Name.Contains("PlcSoftware");
            if (!isPlc) continue;

            var itemName = GetPropString(item, "Name") ?? "";
            var softName = GetPropString(software, "Name") ?? "";
            if (wantedName == "" ||
                string.Equals(deviceName, wantedName, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(softName, wantedName, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(itemName, wantedName, StringComparison.OrdinalIgnoreCase))
            {
                return software;
            }
        }

        var childrenProp = item.GetType().GetProperty("DeviceItems");
        if (childrenProp?.GetValue(item) is IEnumerable children)
        {
            foreach (var child in children)
            {
                var found = FindPlcSoftwareInItem(child, wantedName, deviceName);
                if (found is not null) return found;
            }
        }

        return null;
    }

    private static OpenProjectResult Fail(string code, string message, bool retryable = false) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message, Retryable = retryable },
    };

    private static SaveProjectResult FailSave(string code, string message, bool retryable = false) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message, Retryable = retryable },
    };

    private static ArchiveProjectResult FailArchive(string code, string message, bool retryable = false) => new()
    {
        Ok = false,
        Error = new ToolError { Code = code, Message = message, Retryable = retryable },
    };

    private static object? GetProp(object? obj, string name) =>
        obj?.GetType().GetProperty(name)?.GetValue(obj);

    private static string? GetPropString(object? obj, string name) =>
        GetProp(obj, name)?.ToString();
}
