using GoodServer.Game;
using GoodServer.Game.Cards;
using GoodServer.Game.GameData;
using GoodServer.Game.GameData.Board.Units;
using GoodServer.Library;

namespace GoodServer.Interaction;

public interface IInteractionContext
{
    public Task SendGame(IGameContext context);
    
    public Task<Vector2Int?> ChoosePosition(IReadOnlyList<Vector2Int> choices, Player player);
    public Task<IReadOnlyList<Vector2Int>?> ChooseMultiplePosition(IReadOnlyList<Vector2Int> choices, int min, int max, Player player);
    
    public Task<IUnit?> ChooseUnit(IReadOnlyList<IUnit> units, Player player);
    public Task<IReadOnlyList<IUnit>?> ChooseMultipleUnit(IReadOnlyList<IUnit> units, int min, int max, Player player);
    
    public Task<Card?> ChooseCard(IReadOnlyList<Card> cards, Player player);
    public Task<IReadOnlyList<Card>?> ChooseMultipleCard(IReadOnlyList<Card> cards, int min, int max, Player player);
    
    public Task<TurnMove> GetTurnMove(IGameContext context, Player player); //현재 상태를 보내고, 턴 행동을 받아옴
    
    public Task<List<Card>> GetDeck(Player player);
    
    //서버 쪽에서 "효과에 대한 내용"을 띄울 수 있으면 좋겠어요 -> 일방향 패킷
}