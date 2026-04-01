using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Or_L : IEffect
{
    //카드를 한 장 뽑습니다. 아군 유닛을 선택해 체력을 1 회복시킵니다.
    public string Id => "Or_L"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return data.Board.Cards
            .Where(c => c.Unit.IsPlaced && c.Owner == data.GetCardById(source).Owner)
            .Select(c => EffectTarget.Unit(c.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        data.DrawCard(data.GetCardById(source).Owner, 1);
        CombatUtils.Heal(data.GetCardById(source), 1, data);
        
        owner.Trash.AddCard(card);
    }
}