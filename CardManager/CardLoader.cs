using System.Diagnostics;
using SeaEngine.Common;

namespace SeaEngine.CardManager;

public class CardLoader
{
    private static readonly CardData ErrorCard =
        new CardData("Er_L", "Error Card", "Er_L", UnitType.Leader, 1, 1);

    private readonly Dictionary<string, CardData> _cards = new Dictionary<string, CardData>();

    public CardLoader(string[] cardData)
    {
        //ID	Name	LeaderID	UnitType	Atk	Hp	EffectID	EventID
        
        for (int i = 1; i < cardData.Length; i++)
        {
            string[] data = cardData[i].Split(',');
            if (data[0] == "")
            {
                continue;
            }
            UnitType unitType = data[3] switch
            {
                "L" => UnitType.Leader,
                "R" => UnitType.Rook,
                "P" => UnitType.Pawn,
                "B" => UnitType.Bishop,
                "N" => UnitType.Knight,
                _ => throw new Exception($"Unknown card type: {data[0]}")
            };
            ;
            _cards.Add(data[0], new CardData(
                    data[0],
                    data[1],
                    data[2],
                    unitType, 
                    int.Parse(data[4]),
                    int.Parse(data[5]),
                    data[6] == "" ? null : data[6],
                    data[7] == "" ? null : data[7]
                ));
            Console.WriteLine($"{_cards[data[0]].Id} loaded");
        }
    }

    public CardData GetCard(string cardName)
    {
        return _cards.GetValueOrDefault(cardName, ErrorCard);
    }
}