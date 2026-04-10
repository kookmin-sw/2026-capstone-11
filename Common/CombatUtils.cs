using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.Common;

public static class CombatUtils
{
    public static bool Attack(Card attacker, Card defender, GameData data)
    {
        return Damage(defender, attacker.Unit.Atk, data);
    }

    public static bool Damage(Card target, int amount, GameData data)
    {
        if (amount <= 0) return false;
        target.Unit.Hp -= amount;
        if (target.Unit.Hp > 0) return false;
        
        data.TriggerEvent(target.Data.EventId, "OnDestroy", target.Guid);
        target.Unit.Withdraw();
        return true;
    }

    public static bool Heal(Card target, int amount, GameData data)
    {
        if (amount <= 0) return false;
        target.Unit.Hp += amount;
        if (target.Unit.Hp < target.Unit.MaxHp) return false;
        
        target.Unit.Hp = target.Unit.MaxHp;
        return true;

    }
}