using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class TurnEnd : IEffect
{
    public string Id => "TurnEnd";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return [EffectTarget.None];
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        //TODO : 턴 종료 시 효과 발동되는 것 처리하기.
        data.ActivePlayer = data.Player1 == data.ActivePlayer ? data.Player2 : data.Player1;
        //TODO : 턴 시작 시 효과 발동되는 것 처리하기.
        data.DrawCard(data.ActivePlayer, 2);
    }
}