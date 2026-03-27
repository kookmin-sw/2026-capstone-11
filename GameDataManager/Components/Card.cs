using SeaEngine.CardManager;

namespace SeaEngine.GameDataManager.Components;

public class Card
{
    public readonly Guid Guid = Guid.NewGuid();
    public readonly Player Owner;
    public readonly CardData Data;
    public readonly Unit Unit;

    public Card(CardData data, Player owner)
    {
        Data = data;
        Owner = owner;
        Unit = new Unit(this);
    }

    public override string ToString()
    {
        return $"{Guid} - {Owner.Id} - {Data.Name}";
    }
}