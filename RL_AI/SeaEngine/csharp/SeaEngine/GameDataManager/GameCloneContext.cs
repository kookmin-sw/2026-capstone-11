using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public class GameCloneContext(int playerCapacity = 0, int cardCapacity = 0)
{
    private readonly Dictionary<Player, Player> _playerMap = new(playerCapacity);
    private readonly Dictionary<Card, Card> _cardMap = new(cardCapacity);

    public void Register(Player original, Player cloned)
    {
        _playerMap[original] = cloned;
    }

    public void Register(Card original, Card cloned)
    {
        _cardMap[original] = cloned;
    }

    public Player GetCloned(Player original) => _playerMap[original];

    public Card GetCloned(Card original) => _cardMap[original];

    public Player? TryGetClonedPlayer(Player original)
    {
        return _playerMap.TryGetValue(original, out var cloned) ? cloned : null;
    }

    public Card? TryGetClonedCard(Card original)
    {
        return _cardMap.TryGetValue(original, out var cloned) ? cloned : null;
    }

    public Player GetOrClone(Player original)
    {
        if (_playerMap.TryGetValue(original, out var cloned))
            return cloned;

        return original.Clone(this);
    }

    public Card GetOrClone(Card original)
    {
        if (_cardMap.TryGetValue(original, out var cloned))
            return cloned;

        return original.Clone(this);
    }
}
