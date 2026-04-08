using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.Common;

public static class CombatUtils
{
    public static bool Attack(Card attacker, Card defender, GameData data)
    {
        defender.Unit.Hp -= attacker.Unit.Atk;
        if (defender.Unit.Hp > 0) return false;
        
        data.TriggerEvent(defender.Data.EventId, "OnDestroy", defender.Guid);
        defender.Unit.Withdraw();
        return true;
    }

    public static bool Heal(Card target, int amount, GameData data)
    {
        target.Unit.Hp += amount;
        if (target.Unit.Hp < target.Unit.MaxHp) return false;
        
        target.Unit.Hp = target.Unit.MaxHp;
        return true;

    }
}