using UnityEngine;
using events.client;
using events.ui;

public enum SelectionState
{
    None,
    UnitSelected
}

public class ChessUIController : MonoBehaviour
{
    // View가 생성될 위치를 가리키는 Transform
    public Transform cardViewRoot;
    public Transform boardViewRoot;

    private SelectionState state = SelectionState.None;
    private string selectedUnitUUID;

    // 이벤트 버스
    [SerializeField] private ChessUIEventBus eventBus;

    void Init()
    {
        //this.eventBus = eventBus;

        eventBus.Subscribe<IClientEvents.UnitSelectedEvent>(OnUnitSelected);
        eventBus.Subscribe<IClientEvents.CellSelectedEvent>(OnCellSelected);
    }

    private void OnUnitSelected(IClientEvents.UnitSelectedEvent evt)
    {
        selectedUnitUUID = evt.UnitUUID;
        state = SelectionState.UnitSelected;
    }

    private void OnCellSelected(IClientEvents.CellSelectedEvent evt)
    {
        if (state != SelectionState.UnitSelected)
            return;

        // // Command 생성
        // var cmd = new MoveCommand
        // {
        //     UnitUUID = selectedUnitUUID,
        //     TargetPos = evt.Pos
        // };

        // eventBus.Publish(new CommandCreatedEvent(cmd));

        state = SelectionState.None;
        selectedUnitUUID = null;
    }

    void Start()
    {
        Init(); // 객체 초기화 (테스트용)
    }
}
