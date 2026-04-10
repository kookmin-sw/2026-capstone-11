using Newtonsoft.Json;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager.Converters;

public class CardConverter : JsonConverter<Card>
{
    public override bool CanRead => false;
    public override void WriteJson(JsonWriter writer, Card? value, JsonSerializer serializer)
    {
        if(value == null) return;
        
        writer.WriteStartObject();
        writer.WritePropertyName("Uid");
        writer.WriteValue(value.Guid.ToString());
        writer.WritePropertyName("Id");
        writer.WriteValue(value.Data.Id);
        writer.WritePropertyName("Owner");
        writer.WriteValue(value.Owner.Id);
        
        writer.WritePropertyName("isPlaced");
        writer.WriteValue(value.Unit.IsPlaced);
        writer.WritePropertyName("isMoved");
        writer.WriteValue(value.Unit.IsMoved);
        
        writer.WritePropertyName("X");
        writer.WriteValue(value.Unit.PosX);
        writer.WritePropertyName("Y");
        writer.WriteValue(value.Unit.PosY);
        
        writer.WritePropertyName("Atk");
        writer.WriteValue(value.Unit.Atk);
        writer.WritePropertyName("Hp");
        writer.WriteValue(value.Unit.Hp);
        writer.WritePropertyName("MaxHp");
        writer.WriteValue(value.Unit.MaxHp);
        
        writer.WritePropertyName("Buff");
        writer.WriteStartArray();
        foreach (var status in value.Unit.Statuses)
        {
            writer.WriteStartObject();
            writer.WritePropertyName("Type");
            writer.WriteValue(status.Type.ToString());
            writer.WritePropertyName("Value");
            writer.WriteValue(status.Value);
            writer.WritePropertyName("RemainingTurns");
            writer.WriteValue(status.RemainingTurns);
            writer.WritePropertyName("SourceKey");
            writer.WriteValue(status.SourceKey);
            writer.WriteEndObject();
        }
        writer.WriteEndArray();
        
        writer.WriteEndObject();
    }

    public override Card? ReadJson(JsonReader reader, Type objectType, Card? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}
