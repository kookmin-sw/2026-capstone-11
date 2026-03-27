using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.Common;

public static class CombatUtils
{
    public static bool Attack(Card attacker, Card defender, GameData data)
    {
        //TODO : Event 체크

        defender.Unit.Hp -= attacker.Unit.Atk;
        if (defender.Unit.Hp <= 0)
        {
            defender.Unit.Withdraw();
            return true;
        }
        return false;
    }

    public static bool Heal(Card target, int amount, GameData data)
    {
        //TODO : Event 체크
        
        target.Unit.Hp += amount;
        if (target.Unit.Hp < target.Unit.MaxHp) return false;
        
        target.Unit.Hp = target.Unit.MaxHp;
        return true;

    }
}