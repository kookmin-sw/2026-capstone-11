namespace GoodServer.Game.Effects;

public interface IEffect
{
    string Description { get; }
    Task Execute(IGameContext context);
}