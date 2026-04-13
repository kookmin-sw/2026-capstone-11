using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Tilemaps;
using entity.targetable;
using events.ui;
using events.client;
using ui.view.unit;
using ui.view.board;

public class WorldInputHandler : MonoBehaviour
{
    [SerializeField] private Camera cam;
    // 보드의 타일맵
    [SerializeField] private Tilemap tilemap;

    // 클릭 가능한 레이어    
    [SerializeField] private LayerMask unitLayer;
    [SerializeField] private LayerMask cellLayer;
    [SerializeField] private LayerMask hoverableLayer;

    [SerializeField] private ChessUIEventBus eventBus;

    // 호버중인 대상
    private IHoverable current;

    void Update()
    {
        // 월드 상에서 클릭 상태 감지
        if (Input.GetMouseButtonDown(0))
        {
            // UI 위 클릭이면 무시
            if (EventSystem.current.IsPointerOverGameObject())
                return;

            HandleClick();
        }

        // 월드 상에서 마우스 위치에 따라 호버 상태 업데이트
        HandleHover();
    }

    private void HandleClick()
    {
        var worldPos = cam.ScreenToWorldPoint(Input.mousePosition);
        worldPos.z = 0;

        // 1. 유닛 먼저
        var unitHit = Physics2D.Raycast(worldPos, Vector2.zero, 0f, unitLayer);

        if (unitHit.collider != null)
        {
            var unit = unitHit.collider.GetComponent<UnitView>();
            if (unit != null)
            {
                eventBus.Publish(new IClientEvents.UnitSelectedEvent(unit));
                return;
            }
        }

        // 2. 보드 영역 클릭 체크
        var cellHit = Physics2D.Raycast(worldPos, Vector2.zero, 0f, cellLayer);

        if (cellHit.collider != null)
        {
            var cell = tilemap.WorldToCell(worldPos);

            eventBus.Publish(new IClientEvents.CellSelectedEvent(BoardView.CellToBoard(cell)));
            return;
        }

        // 3. 바깥
        eventBus.Publish(new IClientEvents.EmptySelectedEvent());
    }

    private void HandleHover()
    {
        Vector2 pos = cam.ScreenToWorldPoint(Input.mousePosition);
        var hit = Physics2D.Raycast(pos, Vector2.zero, 0f, hoverableLayer);

        var next = hit.collider?.GetComponent<IHoverable>();

        if (next != current)
        {
            if (current != null)
                eventBus.Publish(new IClientEvents.HoverExitEvent { Target = current });

            if (next != null)
                eventBus.Publish(new IClientEvents.HoverEnterEvent { Target = next });

            current = next;
        }
    }
}