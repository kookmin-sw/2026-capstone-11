using Newtonsoft.Json;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager.Converters;

public class CardZoneConverter : JsonConverter<CardZone>
{
    public override bool CanRead => false;

    public override void WriteJson(JsonWriter writer, CardZone? value, JsonSerializer serializer)
    {
        if (value == null) return;
        writer.WriteStartArray();
        foreach (var card in value.Cards)
        {
            writer.WriteValue(card.Guid.ToString());
        }
        writer.WriteEndArray();
    }

    public override CardZone? ReadJson(JsonReader reader, Type objectType, CardZone? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException(); //Not Readable
    }
}