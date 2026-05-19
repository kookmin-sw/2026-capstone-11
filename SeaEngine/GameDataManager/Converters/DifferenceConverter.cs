using Newtonsoft.Json;
using SeaEngine.GameDataManager.Components.differences;

namespace SeaEngine.GameDataManager.Converters;

public class DifferenceConverter : JsonConverter<Difference>
{
    public override bool CanRead => false;
    
    public override void WriteJson(JsonWriter writer, Difference? value, JsonSerializer serializer)
    {
        if (value == null) return;
        writer.WriteStartArray();
        writer.WriteValue(value.Name);
        foreach (var target in value.Targets)
        {
            writer.WriteValue(target.ToString());
        }
        writer.WriteEndArray();
    }

    public override Difference? ReadJson(JsonReader reader, Type objectType, Difference? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}