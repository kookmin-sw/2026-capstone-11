using UnityEngine;
using ui.tooltip;
using events.client;
using events.ui;

public class TooltipController : MonoBehaviour
{
    [SerializeField] private ChessUIEventBus eventBus;
    [SerializeField] private TooltipEntity tooltipView;

    private void OnEnable()
    {
        eventBus.Subscribe<IClientEvents.HoverEnterEvent>(OnHoverEnter);
        eventBus.Subscribe<IClientEvents.HoverExitEvent>(OnHoverExit);
        tooltipView.Hide(); // 초기에는 툴팁 숨김
    }

    private void OnHoverEnter(IClientEvents.HoverEnterEvent evt)
    {
        var data = evt.Target.GetTooltipData();
        tooltipView.Show(data);
    }

    private void OnHoverExit(IClientEvents.HoverExitEvent evt)
    {
        tooltipView.Hide();
    }
}