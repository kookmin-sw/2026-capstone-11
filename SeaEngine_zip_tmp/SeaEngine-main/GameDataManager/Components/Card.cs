using SeaEngine.CardManager;
using SeaEngine.Common;

namespace SeaEngine.GameDataManager.Components;

public class Card
{
    public readonly Uid Guid = new Uid("C");
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