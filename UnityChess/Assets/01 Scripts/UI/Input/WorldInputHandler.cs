using UnityEngine;
using UnityEngine.EventSystems;
using entity.targetable;
using events.ui;
using events.client;
using System;

public class WorldInputHandler : MonoBehaviour
{
    [SerializeField] private Camera cam;
    [SerializeField] private LayerMask selectableLayer;
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
        Vector2 worldPos = cam.ScreenToWorldPoint(Input.mousePosition);

        var hit = Physics2D.Raycast(worldPos, Vector2.zero, 0f, selectableLayer);

        if (hit.collider == null) return;

        var selectable = hit.collider.GetComponent<ISelectable>();
        selectable?.OnSelected();
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