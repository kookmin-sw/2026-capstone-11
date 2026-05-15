using GoodServer.Game.Cards;
using GoodServer.Game.GameData.Board.Units;

namespace GoodServer.Game;

public class TurnMove
{
    public static readonly TurnMove TurnEnd = new TurnMove(Type.TurnEnd, null, null);
    public enum Type
    {
        UseCard,
        BasicMove,
        TurnEnd,
    }
    
    public readonly Type MoveType;
    
    private readonly IUnit? _unit;
    private readonly Card? _card;

    private TurnMove(Type moveType, IUnit? unit, Card? card)
    {
        MoveType = moveType;
        _unit = unit;
        _card = card;
    }

    public static TurnMove UseCard(Card card)
    {
        return new TurnMove(Type.UseCard, null, card);
    }

    public static TurnMove BasicMove(IUnit unit)
    {
        return new TurnMove(Type.BasicMove, unit, null);
    }

    public Card? GetCard()
    {
        return _card;
    }

    public IUnit? GetUnit()
    {
        return _unit;
    }
}