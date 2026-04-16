using UnityEngine;
using ui.view;
using ui.view.unit;
using events;
using TMPro;
using events.ui;
using ui.view.board;
using UnityEngine.Tilemaps;
using System.Collections.Generic;
using core.actions;   // ActionDTO 네임스페이스
using core.data;    // CardDefinition 네임스페이스

public class TestInit : MonoBehaviour
{
    [SerializeField] private UnitView unitPrefab;
    [SerializeField] private ChessUIEventBus eventBus;
    [SerializeField] private ChessUIController uiController;
    [SerializeField] private CardUnitDB db;

    public Tilemap tilemap;

    void Start()
    {
        CreateTestUnit();
        CreateTestUnit2();

        InjectTestActions();
    }

    private void CreateTestUnit()
    {
        var go = Instantiate(unitPrefab);
        var def = db.Get("Or_R");

        var data = new UnitViewData(
            new ViewID(ViewType.Unit, "unit_1"),
            ViewType.Unit,
            "Or_R",
            def.card.attack,
            def.card.hp,
            new Vector2Int(0, 0)
        );

        go.Init(data, eventBus);
        go.SetDefinition(def);

        go.transform.position = tilemap.GetCellCenterWorld(
            BoardView.BoardToCell(new Vector2Int(0, 0), true)
        );
    }

    private void CreateTestUnit2()
    {
        var go = Instantiate(unitPrefab);
        var def = db.Get("Cl_L");

        var data = new UnitViewData(
            new ViewID(ViewType.Unit, "unit_2"),
            ViewType.Unit,
            "Cl_L",
            def.card.attack,
            def.card.hp,
            new Vector2Int(1, 1)
        );

        go.Init(data, eventBus);
        go.SetDefinition(def);

        go.transform.position = tilemap.GetCellCenterWorld(
            BoardView.BoardToCell(new Vector2Int(1, 1), true)
        );
    }

    private void InjectTestActions()
    {
        var testActions = new List<ActionDTO>
        {
            // unit_1 이동 테스트
            new ActionDTO
            {
                UID = "act_move_unit_1_a",
                EffectID = "DefaultMove",
                Source = "unit_1",
                Target = "0/1"
            },
            new ActionDTO
            {
                UID = "act_move_unit_1_b",
                EffectID = "DefaultMove",
                Source = "unit_1",
                Target = "0/2"
            },
            new ActionDTO
            {
                UID = "act_move_unit_1_c",
                EffectID = "DefaultMove",
                Source = "unit_1",
                Target = "1/0"
            },

            // unit_2 이동 테스트
            new ActionDTO
            {
                UID = "act_move_unit_2_a",
                EffectID = "DefaultMove",
                Source = "unit_2",
                Target = "1/2"
            },
            new ActionDTO
            {
                UID = "act_move_unit_2_b",
                EffectID = "DefaultMove",
                Source = "unit_2",
                Target = "2/1"
            },

            // 턴 종료 테스트
            new ActionDTO
            {
                UID = "act_turn_end",
                EffectID = "TurnEnd",
                Source = "",
                Target = ""
            }
        };

        uiController.SetAvailableActions(testActions);
    }
}