using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine;

public partial class Game
{
    public void Init(string player1Deck, string player2Deck)
    {
        //TODO : Json Parse하게 만들기.
        List<string> player1DeckList = ["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"];
        List<string> player2DeckList = ["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"];
        
        Data.Init(player1DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player1)).ToList(),  
            player2DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player2)).ToList());
        
        Data.Player1.Deck.Shuffle();
        Data.Player2.Deck.Shuffle();
        
        Data.Player1.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(0, 2);
        Data.Player2.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(5, 3);
        
        //TODO : 멀리건 만들기.
        Data.DrawCard(Data.Player1, 3);  
        Data.DrawCard(Data.Player2, 3);  
        
        //TODO : Active Player 랜덤하게 지정하기.(굳이 해야 할까?)
        UpdateActions();
    }
}