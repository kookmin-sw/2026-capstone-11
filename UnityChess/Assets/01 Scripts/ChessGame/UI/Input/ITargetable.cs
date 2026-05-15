namespace entity.targetable
{
    /// <summary>
    /// 툴팁 데이터 구조체
    /// </summary>
    public struct TooltipData
    {
        public string title;
        public string header;
        public string description;

        public TooltipData(string title, string header, string description)
        {
            this.title = title;
            this.header = header;
            this.description = description;
        }
    }

    /// <summary>
    /// 툴팁을 표시할 수 있는 오브젝트(카드, 유닛)이 구현하는 인터페이스
    /// </summary>
    public interface IHoverable
    {
        // 툴팁에 표시할 데이터를 받아옵니다.
        public TooltipData GetTooltipData();
    }

    /// <summary>
    /// 선택될 수 있는 오브젝트(카드, 유닛, 타일)이 구현하는 인터페이스
    /// </summary>
    public interface ISelectable
    {
        public void OnSelected();
    }
}
