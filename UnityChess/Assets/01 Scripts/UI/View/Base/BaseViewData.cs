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

        public override bool Equals(object other)
        {
            return other is ViewID otherId &&
                    Type == otherId.Type &&
                    UUID == otherId.UUID;
        }
        
        public override int GetHashCode()
        {
            return HashCode.Combine(Type, UUID);
        }
    }

    /// <summary>
    /// UI 뷰의 기본 데이터 클래스
    /// </summary>
    [Serializable]
    abstract public class BaseViewData
    {
        public ViewID Id { get; }
        public ViewType Type { get; }
        
        // 공통 유닛 정의
        public string cardId;

        protected BaseViewData(ViewID id, ViewType type)
        {
            Id = id;
            Type = type;
        }
    }
}


