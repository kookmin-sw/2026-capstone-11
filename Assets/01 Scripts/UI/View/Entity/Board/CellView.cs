using events;
using ui.view.unit;
using UnityEngine;

namespace ui.view.board
{
    public class CellViewData : BaseViewData
    {
        public int x;
        public int y;
        public bool HasUnit => unit != null; // 셀에 유닛이 있는지 여부
        public UnitView unit; // 셀에 올라가 있는 유닛
        public CellViewData(ViewID id, ViewType type) : base(id, type)
        {
            
        }
    }

    public class CellView : BaseView
    {
        public CellViewData data;

        public override void Init(BaseViewData baseData, IEventBus eventBus)
        {
            base.Init(baseData, eventBus);
            data = (CellViewData)baseData;
        }

        public override void Subscribe()
        {
            
        }

        public override void UnSubscribe()
        {
            
        }
    }
}
