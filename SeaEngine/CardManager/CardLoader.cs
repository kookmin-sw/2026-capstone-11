using SeaEngine.Common;

namespace SeaEngine.CardManager;

public class CardLoader
{
    private static readonly CardData ErrorCard =
        new CardData("Er_L", "Error Card", "Er_L", UnitType.Leader, 1, 1);
    
    private readonly Dictionary<string, CardData> _cards = new Dictionary<string, CardData>();
    
    public CardLoader(string cardData)
    {
        //TODO : JSON 파싱해서 실제 카드 로드하게 만들기
        _cards.Add("Or_L", new CardData("Or_L", "귤 공주님", "Or_L", UnitType.Leader, 3, 9));
        _cards.Add("Or_B", new CardData("Or_B", "귤 직장인?", "Or_L", UnitType.Bishop, 1, 4));
        _cards.Add("Or_N", new CardData("Or_N", "망상의 기사님", "Or_L", UnitType.Knight, 2, 3));
        _cards.Add("Or_R", new CardData("Or_R", "귤 나무", "Or_L", UnitType.Rook, 1, 3));
        _cards.Add("Or_P", new CardData("Or_P", "귤 요정", "Or_L", UnitType.Pawn, 1, 1, EffectId: "PawnGeneric"));
        
        _cards.Add("Cl_L", new CardData("Cl_L", "샤를로테", "Cl_L", UnitType.Leader, 3, 9));
        _cards.Add("Cl_B", new CardData("Cl_B", "바이올렛", "Cl_B", UnitType.Bishop, 1, 2, EventId: "Cl_Blitz"));
        _cards.Add("Cl_N", new CardData("Cl_N", "아이린", "Cl_N", UnitType.Knight, 2, 2));
        _cards.Add("Cl_R", new CardData("Cl_R", "릴리아", "Cl_R", UnitType.Rook, 1, 3, EventId: "Cl_Blitz"));
        _cards.Add("Cl_P", new CardData("Cl_P", "미스티아", "Cl_P", UnitType.Pawn, 1, 1, EffectId: "PawnGeneric"));
    }

    public CardData GetCard(string cardName)
    {
        return _cards.GetValueOrDefault(cardName, ErrorCard);
    }
}