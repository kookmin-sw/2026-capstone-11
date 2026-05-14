using UnityEngine;
using UnityEngine.EventSystems;
using entity.targetable;
using events.ui;
using events.client;
using ui.view.card;
using System.Collections.Generic;

public class UIInputHandler : MonoBehaviour, IInputHandler
{
    [SerializeField] private Camera cam;
    // 보드의 타일맵
    [SerializeField] private LayerMask cardLayer;
    [SerializeField] private LayerMask hoverableLayer;

    [SerializeField] private ChessUIEventBus eventBus;
    [SerializeField] private EventSystem eventSystem;

    // 호버중인 대상
    private IHoverable current;
    private PointerEventData pointerEventData;
    private List<RaycastResult> raycastResults = new List<RaycastResult>();

    void Awake()
    {
        pointerEventData = new PointerEventData(eventSystem);
    }

    void Update()
    {
        // 월드 상에서 클릭 상태 감지
        if (Input.GetMouseButtonDown(0))
        {
            HandleClick();
        }

        // 월드 상에서 마우스 위치에 따라 호버 상태 업데이트
        HandleHover();
    }

    public void HandleClick()
    {
        var cardHit = FindTopmostUIComponent<CardView>();
        if (cardHit != null)
        {
            eventBus.Publish(new IClientEvents.CardSelectedEvent(cardHit));
        }
    }

    public void HandleHover()
    {
        var next = FindTopmostUIComponent<IHoverable>();

        if (next != current)
        {
            if (current != null)
                eventBus.Publish(new IClientEvents.HoverExitEvent { Target = current });

            if (next != null)
                eventBus.Publish(new IClientEvents.HoverEnterEvent { Target = next });

            current = next;
        }
    }

    private T FindTopmostUIComponent<T>() where T : class
    {
        raycastResults.Clear();

        pointerEventData ??= new PointerEventData(eventSystem);
        
        pointerEventData.position = Input.mousePosition;
        eventSystem.RaycastAll(pointerEventData, raycastResults);

        foreach (var result in raycastResults)
        {
            var target = result.gameObject.GetComponentInParent(typeof(T)) as T;
            if (target != null)
                return target;
        }

        return null;
    }
}