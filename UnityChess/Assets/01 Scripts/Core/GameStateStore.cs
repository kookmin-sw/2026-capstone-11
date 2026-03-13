using System.Collections.Generic;
using UnityEngine;

namespace core
{
    /// <summary>
    /// 게임 내 엔티티의 UUID
    /// </summary>
    public readonly struct EntityID
    {
        public readonly string id;

        public EntityID (string id)
        {
            this.id = id;
        }
    }

    /// <summary>
    /// 카드의 위치
    /// </summary>
    public enum CardZone
    {
        Hand,
        Deck,
        Used
    }

    /// <summary>
    /// 유닛의 보드 내 위치
    /// </summary>
    public struct CellPos
    {
        // 서버 내부 표기에 따라 (x, y) 좌표계 사용
        public int x;
        public int y;

        public CellPos (int x, int y)
        {
            this.x = x;
            this.y = y;
        }
    }

    /// <summary>
    /// 효과 상태를 나타내는 래퍼 클래스
    /// </summary>
    public class EffectState
    {
        public EntityID id;
        // TODO: 효과 상태를 정의하는 속성이 필요함
        public int value; // 효과 값
        public int duration; // 지속 턴
    }

    /// <summary>
    /// 카드 상태를 나타내는 래퍼 클래스
    /// </summary>
    public class CardState
    {
        EntityID id;
        public CardZone zone;

        public CardState (EntityID id, CardZone zone)
        {
            this.id = id;
            this.zone = zone;
        }
    }

    // TODO: 플레이어 상태 클래스 필요

    /// <summary>
    /// 유닛 상태를 나타내는 래퍼 클래스
    /// </summary>
    public class UnitState
    {
        public EntityID id;
        // TODO: 소유 플레이어 정보 필요
        public CellPos position;
        public List<EffectState> effects;

        public UnitState (EntityID id, CellPos position, List<EffectState> effects = null)
        {
            this.id = id;
            this.position = position;
            this.effects = effects ?? new List<EffectState>();
        }
    }

    public class GameStateStore : MonoBehaviour
    {
        // 게임 상태 저장 및 관리 로직 구현
        public Dictionary<EntityID, CardState> MyCards = new Dictionary<EntityID, CardState>();
        public Dictionary<EntityID, UnitState> Units = new Dictionary<EntityID, UnitState>();

        // TODO: State를 업데이트하는 메서드 구현
    }
}