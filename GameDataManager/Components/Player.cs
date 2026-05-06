namespace SeaEngine.GameDataManager.Components;

public class Player(string id)
{
    public readonly string Id = id;
    public CardZone Hand = new CardZone();
    public CardZone Deck = new CardZone();
    public CardZone Trash = new CardZone();

    public Player Clone(GameCloneContext ctx)
    {
        var cloned = new Player(Id);
        ctx.Register(this, cloned);
        cloned.Hand = Hand.Clone(ctx);
        cloned.Deck = Deck.Clone(ctx);
        cloned.Trash = Trash.Clone(ctx);
        return cloned;
    }
}