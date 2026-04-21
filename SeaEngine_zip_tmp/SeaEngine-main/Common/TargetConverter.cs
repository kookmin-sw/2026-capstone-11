using Newtonsoft.Json;
using SeaEngine.GameEffectManager;

namespace SeaEngine.Common;

public class TargetConverter : JsonConverter<EffectTarget>
{
    public override bool CanRead => false;

    public override void WriteJson(JsonWriter writer, EffectTarget? value, JsonSerializer serializer)
    {
        if (value == null) return;
        writer.WriteStartObject();
        switch (value.Type)
        {
            case EffectTarget.Types.Unit:
                writer.WritePropertyName("Type");
                writer.WriteValue("Unit");
                writer.WritePropertyName("Value");
                writer.WriteValue($"{value.Guid}");
                break;
            case EffectTarget.Types.Unit2:
                writer.WritePropertyName("Type");
                writer.WriteValue("Unit2");
                writer.WritePropertyName("Value");
                writer.WriteValue($"{value.Guid}/{value.Guid2}");
                break;
            case EffectTarget.Types.Card:
                writer.WritePropertyName("Type");
                writer.WriteValue("Card");
                writer.WritePropertyName("Value");
                writer.WriteValue($"{value.Guid}");
                break;
            case EffectTarget.Types.Cell:
                writer.WritePropertyName("Type");
                writer.WriteValue("Cell");
                writer.WritePropertyName("Value");
                writer.WriteValue($"{value.PosX}/{value.PosY}");
                break;
            case EffectTarget.Types.None:
                writer.WritePropertyName("Type");
                writer.WriteValue("None");
                writer.WritePropertyName("Value");
                writer.WriteValue("");
                break;
            default:
                throw new ArgumentOutOfRangeException();
        }
        writer.WriteEndObject();
    }

    public override EffectTarget? ReadJson(JsonReader reader, Type objectType, EffectTarget? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}