using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

public interface IAttackEvent : IEvent
{
    public bool BeforeAttack(Uid source, Uid target, GameData data);
    public bool BeforeAttacked(Uid source, Uid target, GameData data);
    
    public bool AfterAttack(Uid source, Uid target, GameData data);
    public bool AfterAttacked(Uid source, Uid target, GameData data);
}