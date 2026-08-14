using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace TiaOpenness.Models;

/// <summary>Stable MCP / agent-facing DTOs for TIA Openness Milestone 1.</summary>
public static class JsonDefaults
{
    public static readonly System.Text.Json.JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
    };
}

public sealed class ToolError
{
    [JsonPropertyName("code")]
    public string Code { get; set; } = "error";

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("retryable")]
    public bool Retryable { get; set; }
}

public sealed class TiaStatusResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("tiaRunning")]
    public bool TiaRunning { get; set; }

    [JsonPropertyName("processCount")]
    public int ProcessCount { get; set; }

    [JsonPropertyName("opennessAvailable")]
    public bool OpennessAvailable { get; set; }

    /// <summary>
    /// True when the current process token includes local group "Siemens TIA Openness".
    /// Account membership alone is not enough — re-login after being added to the group.
    /// </summary>
    [JsonPropertyName("opennessGroupInToken")]
    public bool OpennessGroupInToken { get; set; }

    [JsonPropertyName("tiaVersion")]
    public string? TiaVersion { get; set; }

    [JsonPropertyName("engineeringDll")]
    public string? EngineeringDll { get; set; }

    [JsonPropertyName("connected")]
    public bool Connected { get; set; }

    [JsonPropertyName("projectOpen")]
    public bool ProjectOpen { get; set; }

    [JsonPropertyName("projectPath")]
    public string? ProjectPath { get; set; }

    [JsonPropertyName("projectName")]
    public string? ProjectName { get; set; }

    [JsonPropertyName("mode")]
    public string? Mode { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class OpenProjectResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("projectPath")]
    public string? ProjectPath { get; set; }

    [JsonPropertyName("projectName")]
    public string? ProjectName { get; set; }

    [JsonPropertyName("plcName")]
    public string? PlcName { get; set; }

    [JsonPropertyName("deviceName")]
    public string? DeviceName { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class BlockInfo
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    /// <summary>OB | FB | FC | DB | OTHER</summary>
    [JsonPropertyName("type")]
    public string Type { get; set; } = "OTHER";

    [JsonPropertyName("path")]
    public string? Path { get; set; }

    [JsonPropertyName("programmingLanguage")]
    public string? ProgrammingLanguage { get; set; }

    [JsonPropertyName("number")]
    public int? Number { get; set; }

    [JsonPropertyName("knowHowProtected")]
    public bool KnowHowProtected { get; set; }
}

public sealed class ListBlocksResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("plcName")]
    public string? PlcName { get; set; }

    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("blocks")]
    public List<BlockInfo> Blocks { get; set; } = new();

    [JsonPropertyName("byType")]
    public Dictionary<string, int>? ByType { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class ExportBlockResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("blockName")]
    public string? BlockName { get; set; }

    [JsonPropertyName("blockType")]
    public string? BlockType { get; set; }

    [JsonPropertyName("exportPath")]
    public string? ExportPath { get; set; }

    [JsonPropertyName("exportedCount")]
    public int? ExportedCount { get; set; }

    [JsonPropertyName("failedCount")]
    public int? FailedCount { get; set; }

    [JsonPropertyName("compileMs")]
    public long? CompileMs { get; set; }

    [JsonPropertyName("listMs")]
    public long? ListMs { get; set; }

    [JsonPropertyName("exportMs")]
    public long? ExportMs { get; set; }

    [JsonPropertyName("knowHowProtectedCount")]
    public int? KnowHowProtectedCount { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class ImportBlockResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("xmlPath")]
    public string? XmlPath { get; set; }

    [JsonPropertyName("overwrite")]
    public bool Overwrite { get; set; }

    [JsonPropertyName("importedNames")]
    public List<string>? ImportedNames { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class SaveProjectResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("projectPath")]
    public string? ProjectPath { get; set; }

    [JsonPropertyName("projectName")]
    public string? ProjectName { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class ArchiveProjectResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("projectPath")]
    public string? ProjectPath { get; set; }

    [JsonPropertyName("archivePath")]
    public string? ArchivePath { get; set; }

    [JsonPropertyName("message")]
    public string? Message { get; set; }

    [JsonPropertyName("error")]
    public ToolError? Error { get; set; }
}

public sealed class ExportSkip
{
    [JsonPropertyName("category")]
    public string Category { get; set; } = "";

    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("detail")]
    public string? Detail { get; set; }
}

public sealed class ExportCategoryCount
{
    [JsonPropertyName("exported")]
    public int Exported { get; set; }

    [JsonPropertyName("failed")]
    public int Failed { get; set; }

    [JsonPropertyName("skipped")]
    public int Skipped { get; set; }
}
