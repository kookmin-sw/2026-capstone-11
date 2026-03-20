using UnityEngine;
using ui.view;
using ui.view.unit;
using events;
using TMPro;
using events.ui;

public class TestInit : MonoBehaviour
{
    [SerializeField] private UnitView unitPrefab;
    [SerializeField] private ChessUIEventBus eventBus;

    void Start()
    {
        CreateTestUnit();
        CreateTestUnit2();
    }

    private void CreateTestUnit()
    {
        var go = Instantiate(unitPrefab);

        var data = new UnitViewData(
            new ViewID(ViewType.Unit, "unit_1"),   // UUID 느낌으로
            ViewType.Unit,
            "Test Unit",
            "Knight",
            1,
            3,
            3,
            "None",
            1,
            new Vector2Int(0, 0)
        );

        go.Init(data, eventBus);

        // 위치 대충 잡기 (isometric 변환 나중에)
        go.transform.position = new Vector3(0.5f, 0, 2);
    }

    private void CreateTestUnit2()
    {
        var go = Instantiate(unitPrefab);

        var data = new UnitViewData(
            new ViewID(ViewType.Unit, "unit_2"),   // UUID 느낌으로
            ViewType.Unit,
            "Test Unit 2",
            "Bishop",
            1,
            3,
            3,
            "None",
            1,
            new Vector2Int(0, 0)
        );

        go.Init(data, eventBus);

        // 위치 대충 잡기 (isometric 변환 나중에)
        go.transform.position = new Vector3(1, 1, 2);
    }
}
