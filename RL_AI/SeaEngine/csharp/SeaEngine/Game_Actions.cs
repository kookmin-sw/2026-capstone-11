using SeaEngine.Common;
using SeaEngine.GameEffectManager;

namespace SeaEngine;

public partial class Game
{
    private void UpdateActions()
    {
        _actions = [];
        
        if (Data.Winner != null)
        {
            return;
        }
        
        //01. 활성 플레이어의, 아직 안 움직인 유닛.
        var movableUnits = Data.Board.Cards.Where(c => c.Owner == Data.ActivePlayer && c.Unit is { IsPlaced: true, IsMoved: false });
        foreach(var unit in movableUnits)
        {
            foreach(var target in EffectRegistry.Get("DefaultMove").GetTargets(unit.Guid, Data))
            {
                _actions.Add(new GameAction("DefaultMove", unit.Guid, target));
            }
        }

        var activeHand = Data.ActivePlayer.Hand;
        //02. 활성 플레이어의 패에 있고, 유닛이 소환상태가 아닌 카드
        var summonCards = activeHand.Cards.Where(c => !c.Unit.IsPlaced);
        foreach(var card in summonCards)
        {
            foreach (var target in EffectRegistry.Get("DeployUnit").GetTargets(card.Guid, Data))
            {
                _actions.Add(new GameAction("DeployUnit", card.Guid, target));
            }
        }
        
        //03. 활성 플레이어의 패에 있고, 유닛이 소환상태인 카드
        var effectCards = activeHand.Cards.Where(c => c.Unit.IsPlaced);
        foreach(var card in effectCards)
        {
            foreach (var target in EffectRegistry.Get(card.Data.EffectId).GetTargets(card.Guid, Data))
            {
                _actions.Add(new GameAction(card.Data.EffectId, card.Guid, target));
            }
        }
        
        //04. 턴 종료
        _actions.Add(new GameAction("TurnEnd", Uid.None, EffectTarget.None));
    }

    public void UseAction(Uid actionId)
    {
        var selectedAction = _actions.FirstOrDefault(a => a.Guid == actionId) ?? throw new KeyNotFoundException($"No action with the guid : {actionId}");
        Logger.Log("UseAction", selectedAction, Data);
        EffectRegistry.Get(selectedAction.EffectId).Apply(selectedAction.Source, selectedAction.Target, Data);
        
        UpdateActions();
    }
}