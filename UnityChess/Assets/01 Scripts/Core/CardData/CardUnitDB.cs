using UnityEngine;
using System.Collections.Generic;
using System;

namespace core.data
{
    /// <summary>
    /// 카드 유닛의 기본 정보를 정의하는 데이터 구조
    /// </summary>
    [Serializable]
    public class CardRow
    {
        public string cardId; // Card.csv의 PK
        public string name;
        public string leaderId; // world 구분을 위한 리더 카드의 ID
        public string unitType; // 유닛 클래스

        public int attack;
        public int hp;

        public string effectId; // Effect.csv의 PK
        public string eventId;  // Event.csv의 PK
        
    }

    /// <summary>
    /// 카드 유닛의 액티브 효과에 대한 텍스트를 정의하는 데이터 구조
    /// </summary>
    [Serializable]
    public class EffectRow
    {
        public string effectId; // Effect.csv의 PK
        public string name;
        [TextArea] public string text;
    }

    /// <summary>
    /// 카드 유닛의 패시브 효과, 발동 조건에 대한 텍스트를 정의하는 데이터 구조
    /// </summary>
    [Serializable]
    public class EventRow
    {
        public string eventId; // Event.csv의 PK
        public string name;
        public string timing; // 발동 시점
        [TextArea] public string text;
    }


    /// <summary>
    /// 런타임 조회용을 위해 조립된 카드/유닛 정의
    /// </summary>
    [Serializable]
    public class CardDefinition
    {   
        // csv 파일에서 추출한 원본 데이터
        public CardRow card;
        public EffectRow effect;
        public EventRow evt;

        // CardRow 데이터 접근자
        public string CardId => card.cardId;
        public string Name => card.name;
        public string LeaderId => card.leaderId;
        public string UnitType => card.unitType;
        public int Attack => card.attack;
        public int HP => card.hp;

        // EffectRow 데이터 접근자
        public string EffectId => effect?.effectId ?? card.cardId;
        public string EffectName => effect.name;
        public string EffectText => effect.text;

        // EventRow 데이터 접근자
        public string EventId => evt?.eventId ?? card.cardId;
        public string EventName => evt.name;
        public string EventTiming => evt.timing;
        public string EventText => evt.text;
    }

    [CreateAssetMenu(menuName = "Game/DB/CardUnitDB")]
    public class CardUnitDB : ScriptableObject
    {
        [Header("Raw rows parsed from CSV")]
        [SerializeField] private List<CardRow> cards = new();
        [SerializeField] private List<EffectRow> effects = new();
        [SerializeField] private List<EventRow> events = new();

        private Dictionary<string, CardRow> cardLookup;
        private Dictionary<string, EffectRow> effectLookup;
        private Dictionary<string, EventRow> eventLookup;

        // 조회 최적화를 위한 조립 결과 캐시
        private Dictionary<string, CardDefinition> definitionCache;

        private void OnEnable()
        {
            BuildLookup();
        }

        private void BuildLookup()
        {
            cardLookup = new Dictionary<string, CardRow>();
            effectLookup = new Dictionary<string, EffectRow>(StringComparer.Ordinal);
            eventLookup = new Dictionary<string, EventRow>(StringComparer.Ordinal);
            definitionCache = new Dictionary<string, CardDefinition>();

            foreach (var row in cards)
            {
                if (row == null)
                    continue;

                if (cardLookup.ContainsKey(row.cardId))
                {
                    Debug.LogError($"[CardUnitDB] 중복 CardID: {row.cardId}");
                    continue;
                }

                cardLookup[row.cardId] = row;
            }

            foreach (var row in effects)
            {
                if (row == null || string.IsNullOrWhiteSpace(row.effectId))
                    continue;

                if (effectLookup.ContainsKey(row.effectId))
                {
                    Debug.LogError($"[CardUnitDB] 중복 EffectID: {row.effectId}");
                    continue;
                }

                effectLookup[row.effectId] = row;
            }

            foreach (var row in events)
            {
                if (row == null || string.IsNullOrWhiteSpace(row.eventId))
                    continue;

                if (eventLookup.ContainsKey(row.eventId))
                {
                    Debug.LogError($"[CardUnitDB] 중복 EventID: {row.eventId}");
                    continue;
                }

                eventLookup[row.eventId] = row;
            }

            ValidateReferences();
        }

        private void ValidateReferences()
        {
            foreach (var card in cards)
            {
                if (card == null)
                    continue;

                string resolvedEffectID = ResolveEffectID(card);
                string resolvedEventID = ResolveEventID(card);

                if (!string.IsNullOrEmpty(resolvedEffectID) &&
                    !effectLookup.ContainsKey(resolvedEffectID))
                {
                    Debug.LogWarning(
                        $"[CardUnitDB] CardID {card.cardId} 가 참조하는 EffectID '{resolvedEffectID}' 를 찾을 수 없습니다.");
                }

                if (!string.IsNullOrEmpty(resolvedEventID) &&
                    !eventLookup.ContainsKey(resolvedEventID))
                {
                    Debug.LogWarning(
                        $"[CardUnitDB] CardID {card.cardId} 가 참조하는 EventID '{resolvedEventID}' 를 찾을 수 없습니다.");
                }
            }
        }

        private string ResolveEffectID(CardRow card)
        {
            if (card == null)
                return string.Empty;

            return string.IsNullOrWhiteSpace(card.effectId)
                ? card.cardId.ToString()
                : card.effectId.Trim();
        }

        private string ResolveEventID(CardRow card)
        {
            if (card == null)
                return string.Empty;

            return string.IsNullOrWhiteSpace(card.eventId)
                ? card.cardId.ToString()
                : card.eventId.Trim();
        }

        /// <summary>
        /// CardID를 기준으로 Card + Effect + Event를 조립한 정의 반환
        /// </summary>
        public CardDefinition Get(string cardID)
        {
            if (definitionCache == null || cardLookup == null)
            {
                BuildLookup();
            }

            if (definitionCache.TryGetValue(cardID, out var cached))
                return cached;

            if (!cardLookup.TryGetValue(cardID, out var cardRow))
            {
                Debug.LogError($"[CardUnitDB] CardID 없음: {cardID}");
                return null;
            }

            string effectID = ResolveEffectID(cardRow);
            string eventID = ResolveEventID(cardRow);

            effectLookup.TryGetValue(effectID, out var effectRow);
            eventLookup.TryGetValue(eventID, out var eventRow);

            var definition = new CardDefinition
            {
                card = cardRow,
                effect = effectRow,
                evt = eventRow
            };

            definitionCache[cardID] = definition;
            return definition;
        }

        public bool TryGet(string cardID, out CardDefinition definition)
        {
            definition = Get(cardID);
            return definition != null;
        }

        public IReadOnlyList<CardRow> GetAllCardRows() => cards;
        public IReadOnlyList<EffectRow> GetAllEffectRows() => effects;
        public IReadOnlyList<EventRow> GetAllEventRows() => events;

        public void SetData(
            List<CardRow> newCards,
            List<EffectRow> newEffects,
            List<EventRow> newEvents)
        {
            cards = newCards ?? new List<CardRow>();
            effects = newEffects ?? new List<EffectRow>();
            events = newEvents ?? new List<EventRow>();
            BuildLookup();
        }
    }
}