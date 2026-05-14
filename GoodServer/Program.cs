using GoodServer.Game;
using GoodServer.Game.GameData;

namespace GoodServer;

internal static class Program
{
    private static async Task Main()
    {
        var testGm = new GameManager(new Player("a"), new Player("b"));
        await testGm.RunGame();
    }
}