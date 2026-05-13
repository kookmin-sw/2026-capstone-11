using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Meloly;

[Event]
public class Me_B : IAttackEvent
{
    public string Id => "Me_B";

    public string Timing => "Attack"; 

    public bool Apply(Uid source, GameData data)
    {
        return false;
    }

    public bool BeforeAttack(Uid source, Uid target, GameData data)
    {
        return false;
    }

    public bool BeforeAttacked(Uid source, Uid target, GameData data)
    {
        return false;
    }

    public bool AfterAttack(Uid source, Uid target, GameData data)
    {
        var card = data.GetCardById(source);
        var targetCard = data.GetCardById(target);

        if (!targetCard.Unit.IsPlaced) return false;

        targetCard.Unit.GiveBuff("Infected");
        
        return true;
    }

    public bool AfterAttacked(Uid source, Uid target, GameData data)
    {
        return false;
    }
}