using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace core.data
{
    /// <summary>
    /// 런타임 조회에 활용될 버프의 정의 데이터
    /// </summary>
    [Serializable]
    public class BuffDefinition
    {
        public string id;
        public string name;
        public string description;

        // 툴팁 표시에 참조할 정보
        public bool useAmount;
        public Color textColor = Color.white;

        public string BuildDisplayDesc(int amount)
        {
            if (!useAmount)
                return description;
            
            return string.Format(description, amount);
        }
    }

    [CreateAssetMenu(menuName = "Game/DB/BuffDB")]
    public class BuffDB : ScriptableObject
    {
        [Header("Buff rows parsed from CSV")]
        public List<BuffDefinition> buffs = new();

        private Dictionary<string, BuffDefinition> definitionCache;

        public void BuildLookup()
        {
            definitionCache = new();

            foreach (var buff in buffs)
            {
                if (buff == null || string.IsNullOrWhiteSpace(buff.id))
                    continue;
                
                definitionCache[buff.id] = buff;
            }
        }

        public BuffDefinition Get(string id)
        {
            if (definitionCache == null)
                BuildLookup();

            if (!definitionCache.TryGetValue(id, out var buff))
            {
                Debug.LogError($"[CardUnitDB] CardID 없음: {id}");
                return null;
            }

            return buff;
        }

        public void SetData(List<BuffDefinition> buffs)
        {
            this.buffs = buffs;
            BuildLookup();
        }
    }
}