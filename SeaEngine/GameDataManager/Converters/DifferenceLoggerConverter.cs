using Newtonsoft.Json;
using SeaEngine.GameDataManager.Components.differences;

namespace SeaEngine.GameDataManager.Converters;

public class DifferenceLoggerConverter : JsonConverter<DifferenceLogger>
{
    public override bool CanRead => false;
    
    public override void WriteJson(JsonWriter writer, DifferenceLogger? value, JsonSerializer serializer)
    {
        if (value == null) return;
        writer.WriteStartArray();
        foreach (var differences in value.ProcessDifferences())
        {
            serializer.Serialize(writer, differences);
        }
        writer.WriteEndArray();
    }

    public override DifferenceLogger? ReadJson(JsonReader reader, Type objectType, DifferenceLogger? existingValue,
        bool hasExistingValue, JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}