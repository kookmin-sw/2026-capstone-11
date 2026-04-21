using Newtonsoft.Json;
using SeaEngine.GameEffectManager;

namespace SeaEngine.Common;

public class ActionConverter : JsonConverter<GameAction>
{
    public override bool CanRead => false;

    public override void WriteJson(JsonWriter writer, GameAction? value, JsonSerializer serializer)
    {
        if(value == null) return;
        
        writer.WriteStartObject();
        writer.WritePropertyName("Uid");
        writer.WriteValue(value.Guid.ToString());
        writer.WritePropertyName("EffectId");
        writer.WriteValue(value.EffectId);
        writer.WritePropertyName("Source");
        writer.WriteValue(value.Source.ToString());
        writer.WritePropertyName("Target");
        serializer.Serialize(writer, value.Target);
        writer.WriteEndObject();
    }

    public override GameAction? ReadJson(JsonReader reader, Type objectType, GameAction? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}