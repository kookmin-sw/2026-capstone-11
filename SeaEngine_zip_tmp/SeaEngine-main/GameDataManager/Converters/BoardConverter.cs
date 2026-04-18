using Newtonsoft.Json;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager.Converters;

public class BoardConverter : JsonConverter<Board>
{
    public override bool CanRead => false;

    public override void WriteJson(JsonWriter writer, Board? value, JsonSerializer serializer)
    {
        if(value == null) return;
        
        writer.WriteStartArray();
        foreach (var card in value.Cards)
        {
            serializer.Serialize(writer, card);
        }
        writer.WriteEndArray();
    }

    public override Board? ReadJson(JsonReader reader, Type objectType, Board? existingValue, bool hasExistingValue,
        JsonSerializer serializer)
    {
        throw new NotImplementedException();
    }
}