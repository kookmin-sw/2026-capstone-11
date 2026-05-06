using SeaEngine.CardManager;
using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameDataManager.Components;

public class Card
{
    public readonly Uid Guid;
    public readonly Player Owner;
    public readonly CardData Data;
    public readonly Unit Unit;

    public Card(CardData data, Player owner, UidFactory uidFactory)
    {
        Data = data;
        Owner = owner;
        Unit = new Unit(this);
        Guid = uidFactory.Next();
    }

    private Card(Uid guid, CardData data, Player owner, Unit unit)
    {
        Guid = guid;
        Data = data;
        Owner = owner;
        Unit = unit;
    }

    public Card Clone(GameCloneContext ctx)
    {
        var clonedOwner = ctx.GetCloned(Owner);
        var clonedUnit = Unit.Clone();
        var cloned = new Card(Guid, Data, clonedOwner, clonedUnit);
        clonedUnit.Card = cloned;
        ctx.Register(this, cloned);
        return cloned;
    }

    public override string ToString()
    {
        return $"{Guid} - {Owner.Id} - {Data.Name}";
    }
}
