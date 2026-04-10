using SeaEngine.Common;
using System.Text;

namespace SeaEngine.CardManager;

public class CardLoader
{
    private static readonly CardData ErrorCard =
        new CardData("Er_L", "Error Card", "Er_L", UnitType.Leader, 1, 1);
    
    private readonly Dictionary<string, CardData> _cards = new Dictionary<string, CardData>();
    
    public CardLoader(string cardData)
    {
        if (!TryLoadFromCsv(cardData))
        {
            LoadFallbackCards();
        }
    }

    public CardData GetCard(string cardName)
    {
        return _cards.GetValueOrDefault(cardName, ErrorCard);
    }

    private void LoadFallbackCards()
    {
        _cards.Clear();
        _cards.Add("Or_L", new CardData("Or_L", "귤 공주님", "Or_L", UnitType.Leader, 3, 9));
        _cards.Add("Or_B", new CardData("Or_B", "귤 직장인?", "Or_L", UnitType.Bishop, 1, 4));
        _cards.Add("Or_N", new CardData("Or_N", "망상의 기사님", "Or_L", UnitType.Knight, 2, 3));
        _cards.Add("Or_R", new CardData("Or_R", "귤 나무", "Or_L", UnitType.Rook, 1, 3));
        _cards.Add("Or_P", new CardData("Or_P", "귤 요정", "Or_L", UnitType.Pawn, 1, 1, EffectId: "PawnGeneric"));

        _cards.Add("Cl_L", new CardData("Cl_L", "샤를로테", "Cl_L", UnitType.Leader, 3, 9));
        _cards.Add("Cl_B", new CardData("Cl_B", "바이올렛", "Cl_L", UnitType.Bishop, 1, 2));
        _cards.Add("Cl_N", new CardData("Cl_N", "아이린", "Cl_L", UnitType.Knight, 2, 2));
        _cards.Add("Cl_R", new CardData("Cl_R", "릴리아", "Cl_L", UnitType.Rook, 1, 3));
        _cards.Add("Cl_P", new CardData("Cl_P", "미스티아", "Cl_L", UnitType.Pawn, 1, 1, EffectId: "PawnGeneric"));
    }

    private bool TryLoadFromCsv(string cardData)
    {
        if (string.IsNullOrWhiteSpace(cardData)) return false;
        if (!File.Exists(cardData)) return false;

        var lines = File.ReadAllLines(cardData, Encoding.UTF8);
        var headerIndex = Array.FindIndex(lines, line => line.StartsWith("CardID,", StringComparison.OrdinalIgnoreCase));
        if (headerIndex < 0) return false;

        var headers = SplitCsvLine(lines[headerIndex]).ToList();
        var headerMap = headers
            .Select((name, index) => new { name = name.Trim(), index })
            .Where(x => !string.IsNullOrWhiteSpace(x.name))
            .ToDictionary(x => x.name, x => x.index);

        if (!headerMap.ContainsKey("CardID")) return false;

        foreach (var line in lines.Skip(headerIndex + 1))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            var row = SplitCsvLine(line).ToList();
            var cardId = NormalizeCardId(GetColumn(row, headerMap, "CardID"));
            if (string.IsNullOrWhiteSpace(cardId)) continue;
            if (!(cardId.StartsWith("Or_") || cardId.StartsWith("Cl_"))) continue;

            var name = GetColumn(row, headerMap, "Name");
            var leaderId = cardId.StartsWith("Or_") ? "Or_L" : "Cl_L";
            var role = ParseUnitType(GetColumn(row, headerMap, "Role"));
            var atk = ParseInt(GetColumn(row, headerMap, "Attack"));
            var hp = ParseInt(GetColumn(row, headerMap, "Life"));
            var effectId = role == UnitType.Pawn ? "PawnGeneric" : cardId;
            var eventId = cardId;

            _cards[cardId] = new CardData(cardId, name, leaderId, role, atk, hp, effectId, eventId);
        }

        return _cards.Count > 0;
    }

    private static string GetColumn(IReadOnlyList<string> row, IReadOnlyDictionary<string, int> headerMap, string name)
    {
        return headerMap.TryGetValue(name, out var index) && index < row.Count ? row[index].Trim() : "";
    }

    private static int ParseInt(string value)
    {
        return int.TryParse(value, out var parsed) ? parsed : 0;
    }

    private static UnitType ParseUnitType(string roleValue)
    {
        return roleValue.Trim() switch
        {
            "0" => UnitType.Leader,
            "1" => UnitType.Bishop,
            "2" => UnitType.Knight,
            "3" => UnitType.Rook,
            "4" => UnitType.Pawn,
            _ => UnitType.Leader,
        };
    }

    private static string NormalizeCardId(string cardId)
    {
        cardId = cardId.Trim();
        return cardId switch
        {
            "Or_K" => "Or_N",
            "Cl_K" => "Cl_N",
            _ => cardId,
        };
    }

    private static IEnumerable<string> SplitCsvLine(string line)
    {
        var current = new StringBuilder();
        var inQuotes = false;
        for (var i = 0; i < line.Length; i++)
        {
            var ch = line[i];
            if (ch == '"')
            {
                if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                {
                    current.Append('"');
                    i += 1;
                }
                else
                {
                    inQuotes = !inQuotes;
                }
                continue;
            }

            if (ch == ',' && !inQuotes)
            {
                yield return current.ToString();
                current.Clear();
                continue;
            }

            current.Append(ch);
        }
        yield return current.ToString();
    }
}
