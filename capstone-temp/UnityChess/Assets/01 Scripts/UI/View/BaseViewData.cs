using System;

namespace ui.view
{
    /// <summary>
    /// UI 요소의 타입
    /// </summary>
    public enum ViewType
    {
        Card,
        Unit,
        Cell,
        HUD
    }

    /// <summary>
    /// HUD UI의 종류 구분
    /// </summary>
    public enum HudSlot
    {
        Turn,
        Mana,
        PlayerInfo,
        TurnEndButton
    }

    /// <summary>
    ///  UI 요소를 표현하는 View의 식별자
    /// </summary>
    [Serializable]
    public struct ViewID
    {
        public ViewType Type;
        public string UUID;

        // ViewID의 생성자
        public ViewID(ViewType type, string uuid)
        {
            Type = type;
            UUID = uuid;
        }

        /// <summary>
        /// 셀 위치를 나타내는 ViewID
        /// </summary>
        /// <param name="pos"> 셀의 위치 (예: "a1")</param>
        /// <returns></returns>
        public static ViewID Cell(string pos)
            => new(ViewType.Cell, pos);

        /// <summary>
        /// 카드 뷰의 ViewID
        /// </summary>
        /// <param name="uuid"> 카드 UUID </param>
        /// <returns></returns>
        public static ViewID Card(string uuid)
            => new(ViewType.Card, uuid);

        /// <summary>
        /// 유닛 뷰의 ViewID
        /// </summary>
        /// <param name="uuid"> 유닛 UUID </param>
        /// <returns></returns>
        public static ViewID Unit(string uuid)
            => new(ViewType.Unit, uuid);
        
        /// <summary>
        /// HUD 뷰의 ViewID
        /// </summary>
        /// <param name="uuid"> HUD UUID</param>
        /// <returns></returns>
        public static ViewID Hud(string uuid)
            => new(ViewType.HUD, uuid);
    }

    /// <summary>
    /// UI 뷰의 기본 데이터 클래스
    /// </summary>
    [Serializable]
    abstract public class BaseViewData
    {
        public ViewID Id { get; }
        public ViewType Type { get; }

        protected BaseViewData(ViewID id, ViewType type)
        {
            Id = id;
            Type = type;
        }
    }
}


