using UnityEngine;
using System.Collections.Generic;

namespace core
{
    [System.Serializable]
    public class CardDefinition
    {
        public int cardID; // Key

        public string name;
        public int world;      // deckId
        public string role;

        public int attack;
        public int life;

        public string textCondition;
        public string textName;
        public string text;

        public string effectName;
        public string effect;
    }

    [CreateAssetMenu(menuName = "Game/DB/CardUnitDB")]
    public class CardUnitDB : ScriptableObject
    {
        [SerializeField] private List<CardDefinition> data = new();

        private Dictionary<int, CardDefinition> lookup;

        private void OnEnable()
        {
            BuildLookup();
        }

        /// <summary>
        /// data 리스트를 기반으로 lookup 딕셔너리를 구축
        /// </summary>
        private void BuildLookup()
        {
            lookup = new Dictionary<int, CardDefinition>();

            foreach (var d in data)
            {
                if (lookup.ContainsKey(d.cardID))
                {
                    Debug.LogError($"중복 CardID: {d.cardID}");
                    continue;
                }

                lookup[d.cardID] = d;
            }
        }

        /// <summary>
        /// 지정된 CardID에 해당하는 CardDefinition을 반환
        /// </summary>
        /// <param name="cardID">조회할 카드 ID</param>
        /// <returns></returns>
        public CardDefinition Get(int cardID)
        {
            if (lookup.TryGetValue(cardID, out var def))
                return def;

            Debug.LogError($"CardID 없음: {cardID}");
            return null;
        }

        public void SetData(List<CardDefinition> newData)
        {
            data = newData;
            BuildLookup();
        }   
    }
}