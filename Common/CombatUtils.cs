using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;
using SeaEngine.GameDataManager.Components.differences;
using SeaEngine.GameEffectManager;

namespace SeaEngine.Common;

public static class CombatUtils
{
    public static void GiveBuff(Card target, string buff, GameData data, int amount = 1)
    {
        target.Unit.GiveBuff(buff, amount);
        data.DifferenceLogger.LogDifference(new Difference("ApplyBuff", 
            [EffectTarget.Card(target.Guid), EffectTarget.String(buff), EffectTarget.String($"{amount}")]));
    }

    public static void RemoveBuff(Card target, string buff, GameData data)
    {
        target.Unit.RemoveBuff(buff);
        data.DifferenceLogger.LogDifference(new Difference("RemoveBuff", 
            [EffectTarget.Card(target.Guid), EffectTarget.String(buff)]));
    }
    
    public static bool Attack(Card attacker, Card defender, GameData data)
    {
        data.TriggerBeforeAttackEvent(attacker.Data.EventId, attacker.Guid, defender.Guid);
        data.TriggerBeforeAttackedEvent(defender.Data.EventId, attacker.Guid, defender.Guid);
        var isDestroyed = Damage(defender, attacker.Unit.Atk, data);
        data.DifferenceLogger.LogDifference(new Difference("AttackUnit",
            [EffectTarget.Card(defender.Guid), EffectTarget.Card(attacker.Guid)]));
        data.TriggerAfterAttackEvent(attacker.Data.EventId, attacker.Guid, defender.Guid);
        data.TriggerAfterAttackedEvent(defender.Data.EventId, attacker.Guid, defender.Guid);
        return isDestroyed;
    }

    public static bool Damage(Card target, int amount, GameData data)
    {
        if (amount <= 0) return false;
        target.Unit.Hp -= amount;
        data.DifferenceLogger.LogDifference(new Difference("DamageUnit",
            [EffectTarget.Card(target.Guid), EffectTarget.String($"{amount}")]));
        if (target.Unit.Hp > 0) return false;
        
        data.TriggerEvent(target.Data.EventId, "OnDestroy", target.Guid);
        data.Board.WithdrawCard(target);

        if (target.Data.UnitType == UnitType.Leader)
        {
            data.Winner = target.Owner == data.Player1 ? data.Player2 : data.Player1;
        }
        return true;
    }

    public static bool Heal(Card target, int amount, GameData data)
    {
        if (amount <= 0) return false;
        target.Unit.Hp += amount;
        data.DifferenceLogger.LogDifference(new Difference("HealUnit",
            [EffectTarget.Card(target.Guid), EffectTarget.String($"{amount}")]));
        if (target.Unit.Hp < target.Unit.MaxHp) return false;
        
        target.Unit.Hp = target.Unit.MaxHp;
        return true;

    }
}