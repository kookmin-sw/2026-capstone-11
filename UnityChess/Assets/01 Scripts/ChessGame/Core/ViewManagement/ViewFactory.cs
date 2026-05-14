using UnityEngine;
using UnityEngine.UI;
using ui.view;
using System;
using System.Collections.Generic;
using events.ui;
using core.data;
using ui.view.board;
using ui.view.card;
using ui.view.unit;
using Core.StateManagement;
using Game.Network;

namespace core.UI
{
    [Serializable]
    public struct PrefabKey
    {
        public ViewType Type;
        public string defId;
    }

    /// <summary>
    /// 유닛 뷰 스프라이트와 뷰 ID를 연결하는 엔트리 클래스
    /// </summary>
    [Serializable]
    public class ViewSpriteEntry
    {
        public PrefabKey key;
        public Sprite[] Sprites;
    }

    /// <summary>
    /// 뷰를 생성하고 파괴하는 팩토리 클래스
    /// </summary>  
    public class ViewFactory : MonoBehaviour
    {
        [Header("References")]
        [SerializeField]
        private ViewRegistry registry;
        [SerializeField]
        private ChessUIEventBus UIEventBus;

        [Header("DB")]
        [SerializeField]
        private CardUnitDB cardDB;
        [SerializeField]
        private BuffDB buffDB;

        [Header("Prefabs")]
        [SerializeField]
        private GameObject UnitBasePrefab;
        [SerializeField]
        private GameObject CardBasePrefab;
        
        [Header("Sprites")]
        [SerializeField]
        private List<ViewSpriteEntry> SpriteEntries;
        [SerializeField]
        private Sprite[] auroraSprites; // 유닛 바닥에 띄우는 클래스 구분 스프라이트

        // TODO: 아트 작업 완료 이후 각 유닛/카드에 맞는 스프라이트를 자동 연결할 수 있도록 개선
        private Dictionary<PrefabKey, Sprite[]> SpriteDict = new Dictionary<PrefabKey, Sprite[]>();

        // 게임 시작 시 프리팹 엔트리를 딕셔너리에 등록
        public void Init()
        {
            foreach (var entry in SpriteEntries)
            {
                if (entry == null || entry.Sprites == null)
                    continue;
                
                SpriteDict[entry.key] = entry.Sprites;
            }
        }
        
        public IView Create(BaseViewData data, Transform parent)
        {
            if (registry.Contains(data.Id))
                throw new Exception($"{data.Id} 뷰가 이미 존재합니다.");
            
            var prefab = data.Type == ViewType.Unit ? UnitBasePrefab : CardBasePrefab;

            var go = Instantiate(prefab, parent);
            go.transform.SetParent(parent, false);
            
            var view = go.GetComponent<IView>();

            view.Init(data, UIEventBus);
            view.SetDefinition(cardDB.Get(data.cardId));

            registry.Register(view, data.Id);

            return view;
        }

        public void Destroy(ViewID id)
        {
            if (!registry.Contains(id))
                throw new Exception($"{id} 뷰가 존재하지 않습니다.");

            var view = registry.Get(id);
            registry.Unregister(id);
            Destroy(((MonoBehaviour)view).gameObject);
        }

        public void DestroyAll()
        {
            var ids = registry.GetAllIds();
            foreach (var id in ids)
            {
                Destroy(id);
            }
        }


        // 스냅샷 상태를 받아온 뒤 뷰를 재구성 하기 위해 필요한 메서드들
        // 이후 수정 가능성 있음
        public void RebuildFromState(
            GameStateStore state,
            string localPlayerId,
            string opponentPlayerId,
            Transform boardParent,
            Transform handParent,
            bool isLocalPlayerP1)
        {
            if (state == null)
            {
                Debug.LogError("[ViewFactory] state is null.");
                return;
            }

            DestroyAll();

            CreateBoardViews(state, localPlayerId, boardParent, isLocalPlayerP1);
            CreateBoardViews(state, opponentPlayerId, boardParent, isLocalPlayerP1);
            CreateHandViews(state, localPlayerId, handParent);
        }

        private void CreateBoardViews(GameStateStore state, string ownerId, Transform boardParent, bool isLocalPlayerP1)
        {
            var units = state.GetPlacedUnits(ownerId);

            foreach (var unit in units)
            {
                var data = new UnitViewData(
                    id: new ViewID(ViewType.Unit, unit.id.id),
                    type: ViewType.Unit,
                    cardId: unit.cardId,
                    curAttack: unit.curAttack,
                    curHP: unit.curHp,
                    pos: unit.position,
                    buffs: ResolveBuffList(unit.buffs)
                );

                bool isMyUnit = state.LocalPlayerId == ownerId;
                var view = Create(data, boardParent);

                if (view is MonoBehaviour mb)
                {
                    var boardView = boardParent.GetComponent<BoardView>();
                    var cell = BoardView.BoardToCell(unit.position, isLocalPlayerP1);
                    var worldPos = boardView.tilemap.GetCellCenterWorld(cell);
                    
                    mb.transform.position = worldPos;
                }

                var key = new PrefabKey { Type = data.Type, defId = data.cardId };
                var unitView = view as UnitView;

                // 플레이어 자신의 유닛인지 확인하고 해당하는 스프라이트를 설정
                unitView.SetUnitSprite(isMyUnit ? SpriteDict[key][0] : SpriteDict[key][1]);
                SetClassSprite(unitView, isMyUnit);
            }
        }

        private void CreateHandViews(GameStateStore state, string playerId, Transform handParent)
        {
            var hand = state.GetHand(playerId);

            foreach (var uid in hand)
            {
                if (!state.TryGetUnit(uid, out var entity))
                    continue;

                var data = new CardViewData(
                    id: new ViewID(ViewType.Card, uid.id),
                    type: ViewType.Card,
                    cardId: entity.cardId
                );

                var view = Create(data, handParent);

                var key = new PrefabKey { Type = data.Type, defId = data.cardId };
                var cardView = view as CardView;

                cardView.SetCardSprite(SpriteDict[key][0]);
            }
        }

        private void SetClassSprite(UnitView unitView, bool isMyUnit)
        {
            var unitClass = cardDB.Get(unitView.data.cardId).UnitType;

            // 유닛 클래스에 따라 클래스 스프라이트 설정
            switch (unitClass)
            {
                case UnitType.Leader:
                    unitView.classSprite.sprite = auroraSprites[0];
                    break;
                case UnitType.Bishop:
                    unitView.classSprite.sprite = auroraSprites[1];
                    break;
                case UnitType.Knight:
                    unitView.classSprite.sprite = auroraSprites[2];
                    break;
                case UnitType.Rook:
                    unitView.classSprite.sprite = auroraSprites[3];
                    break;
                case UnitType.Pawn:
                    unitView.classSprite.sprite = auroraSprites[4];
                    break;
                default:
                    Debug.LogWarning($"알 수 없는 유닛 클래스: {unitClass}");
                    break;
            }

            // 아군 유닛을 흰색으로 하고, 상대 유닛을 검은색으로 설정
            unitView.classSprite.color = isMyUnit ? Color.white : Color.black;
        }

        private List<UnitViewData.BuffViewData> ResolveBuffList(List<EffectState> buffs)
        {
            var data = new List<UnitViewData.BuffViewData>();

            foreach (var buff in buffs)
            {
                data.Add(new UnitViewData.BuffViewData(buffDB.Get(buff.id), buff.amount));
            }

            return data;
        }

        void Awake()
        {
            Init();
        }
    }
}
