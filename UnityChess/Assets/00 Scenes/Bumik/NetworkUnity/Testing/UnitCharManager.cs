using UnityEngine;

using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

public class UnitCharManager : MonoBehaviour
{
    [System.Serializable]
    private class BoardUnitData
    {
        public string uid;
        public string id;
        public int x;
        public int y;
        public int hp;
        public int atk;
    }

    [Header("References")]
    [SerializeField] private RectTransform boardRoot;
    [SerializeField] private UnitChar unitCharPrefab;

    [Header("Test Json")]
    [TextArea(10, 30)]
    [SerializeField] private string jsonString;

    [Header("Option")]
    [SerializeField] private bool renderOnStart = true;
    [SerializeField] private bool invertY = false;

    private const int Width = 6;
    private const int Height = 6;

    private readonly List<UnitChar> cells = new List<UnitChar>(Width * Height);

    private void Start()
    {
        InitGrid();

        if (renderOnStart)
            RenderBoard(jsonString);
    }

    [ContextMenu("Init Grid")]
    public void InitGrid()
    {
        if (boardRoot == null || unitCharPrefab == null)
        {
            Debug.LogWarning("boardRoot 또는 unitCharPrefab 이 비어있습니다.");
            return;
        }

        ClearChildren();
        cells.Clear();

        for (int i = 0; i < Width * Height; i++)
        {
            UnitChar cell = Instantiate(unitCharPrefab, boardRoot);
            cell.name = $"UnitChar_{i}";
            cell.SetEmpty();
            cells.Add(cell);
        }
    }

    [ContextMenu("Render Board")]
    public void RenderBoard()
    {
        RenderBoard(jsonString);
    }

    public void RenderBoard(string json)
    {
        if (cells.Count != Width * Height)
            InitGrid();

        for (int i = 0; i < cells.Count; i++)
            cells[i].SetEmpty();

        List<BoardUnitData> units = ParseBoard(json);

        foreach (var unit in units)
        {
            if (unit.x < 0 || unit.y < 0 || unit.x >= Width || unit.y >= Height)
                continue;

            int row = invertY ? (Height - 1 - unit.y) : unit.y;
            int index = row * Width + unit.x;

            if (index < 0 || index >= cells.Count)
                continue;

            cells[index].SetData(unit.uid, unit.id, unit.hp, unit.atk);
        }
    }

    private List<BoardUnitData> ParseBoard(string json)
    {
        var result = new List<BoardUnitData>();

        if (string.IsNullOrEmpty(json))
            return result;

        JObject root = JObject.Parse(json);
        JArray boardArray = root["Data"]?["Board"] as JArray;

        if (boardArray == null)
            return result;

        foreach (JObject item in boardArray)
        {
            int x = item["X"]?.Value<int>() ?? -1;
            int y = item["Y"]?.Value<int>() ?? -1;

            if (x == -1 || y == -1)
                continue;

            result.Add(new BoardUnitData
            {
                uid = item["Uid"]?.ToString() ?? "",
                id = item["Id"]?.ToString() ?? "",
                x = x,
                y = y,
                hp = item["Hp"]?.Value<int>() ?? 0,
                atk = item["Atk"]?.Value<int>() ?? 0
            });
        }

        return result;
    }

    private void ClearChildren()
    {
        for (int i = boardRoot.childCount - 1; i >= 0; i--)
        {
            Destroy(boardRoot.GetChild(i).gameObject);
        }
    }
}
