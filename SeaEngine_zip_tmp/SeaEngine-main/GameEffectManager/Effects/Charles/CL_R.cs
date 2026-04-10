using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Cl_R : IEffect
{
    //이동 범위 내 적을 하나 선택해 공격합니다.
    // 선택한 적 방향으로 한 칸 이동합니다.
    // 이동할 수 없었다면, 선택한 적을 다시 한 번 공격
    public string Id => "Cl_R"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var defender = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        CombatUtils.Attack(card, defender, data);
        
        int dx = Math.Sign(defender.Unit.PosX - card.Unit.PosX);
        int dy = Math.Sign(defender.Unit.PosY - card.Unit.PosY);

        if (card.Unit.PosX + dx is >= 0 and < Board.BoardSize && 
            card.Unit.PosY + dy is >= 0 and < Board.BoardSize && 
            data.Board.IsEmptyCell(card.Unit.PosX + dx, card.Unit.PosY + dy))
        {
            card.Unit.Move(card.Unit.PosX + dx, card.Unit.PosY + dy);
        }
        else
        {
            CombatUtils.Attack(card, defender, data);
        }
        
        owner.Trash.AddCard(card);
    }
}