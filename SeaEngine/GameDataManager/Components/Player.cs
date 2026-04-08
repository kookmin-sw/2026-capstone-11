namespace SeaEngine.GameDataManager.Components;

public class Player(string id)
{
    public readonly string Id = id;
    public readonly CardZone Hand = new CardZone();
    public readonly CardZone Deck = new CardZone();
    public readonly CardZone Trash = new CardZone();
}