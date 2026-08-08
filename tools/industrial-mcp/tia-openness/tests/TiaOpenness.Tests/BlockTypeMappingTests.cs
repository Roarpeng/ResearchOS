using TiaOpenness.Models;
using TiaOpenness.Server;

namespace TiaOpenness.Tests;

public class BlockTypeMappingTests
{
    [Theory]
    [InlineData("OB", "OB1", "OB")]
    [InlineData("OrganizationBlock", "Main", "OB")]
    [InlineData("FB", "FB_Motor", "FB")]
    [InlineData("FunctionBlock", "Motor", "FB")]
    [InlineData("FC", "FC10", "FC")]
    [InlineData("FC", "Helpers", "FC")]
    [InlineData("GlobalDB", "DB_Data", "DB")]
    [InlineData("InstanceDB", "FB_Motor_DB", "DB")]
    [InlineData("ArrayDB", "DB_Array", "DB")]
    [InlineData("UnknownThing", "X", "OTHER")]
    public void MapBlockType_Classifies_Openness_Types(string clr, string name, string expected)
    {
        Assert.Equal(expected, BlockService.MapBlockType(clr, name));
    }

    [Fact]
    public void MapBlockType_ObNameHeuristic()
    {
        Assert.Equal("OB", BlockService.MapBlockType("SomethingElse", "OB100"));
    }
}

public class TiaStatusTests
{
    [Fact]
    public void GetStatus_Reports_Openness_Dll_When_V19_Installed()
    {
        using var connection = new TiaConnection("V19");
        var status = connection.GetStatus();

        Assert.True(status.Ok);
        Assert.Equal("V19", status.TiaVersion);
        // This machine has Portal V19 PublicAPI; keep assertion soft if missing.
        if (status.OpennessAvailable)
        {
            Assert.False(string.IsNullOrWhiteSpace(status.EngineeringDll));
            Assert.True(File.Exists(status.EngineeringDll));
        }
    }

    [Fact]
    public void OpenProject_Rejects_Missing_File()
    {
        using var connection = new TiaConnection("V19");
        var projects = new ProjectService(connection);
        var result = projects.OpenProject(@"C:\does\not\exist\Line.ap19");

        Assert.False(result.Ok);
        Assert.Equal("not_found", result.Error?.Code);
    }

    [Fact]
    public void ListBlocks_Requires_Open_Project()
    {
        using var connection = new TiaConnection("V19");
        var projects = new ProjectService(connection);
        var blocks = new BlockService(projects);
        var result = blocks.ListBlocks();

        Assert.False(result.Ok);
        Assert.Equal("invalid_argument", result.Error?.Code);
    }

    [Fact]
    public void ImportBlock_Requires_Open_Project()
    {
        using var connection = new TiaConnection("V19");
        var projects = new ProjectService(connection);
        var blocks = new BlockService(projects);
        var result = blocks.ImportBlock(@"C:\temp\block.xml");

        Assert.False(result.Ok);
        Assert.Equal("invalid_argument", result.Error?.Code);
    }

    [Fact]
    public void SaveProject_Requires_Open_Project()
    {
        using var connection = new TiaConnection("V19");
        var projects = new ProjectService(connection);
        var result = projects.SaveProject();

        Assert.False(result.Ok);
        Assert.Equal("invalid_argument", result.Error?.Code);
    }

    [Fact]
    public void Models_Serialize_CamelCase()
    {
        var payload = new TiaStatusResult
        {
            Ok = true,
            TiaRunning = false,
            OpennessAvailable = true,
            TiaVersion = "V19",
        };
        var json = System.Text.Json.JsonSerializer.Serialize(payload, JsonDefaults.Options);
        Assert.Contains("\"ok\":true", json);
        Assert.Contains("\"tiaRunning\":false", json);
        Assert.Contains("\"opennessAvailable\":true", json);
    }
}
