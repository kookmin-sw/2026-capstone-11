using UnityEngine;
using System.Collections.Generic;

namespace core.data
{
    [CreateAssetMenu(menuName = "Game/DB/DeckDB")]
    public class DeckDB : ScriptableObject
    {
        public string deckId; // 리더 고유 prefix
        public string leaderId;
        public string displayName;
        public List<string> cardIds;
    }
}