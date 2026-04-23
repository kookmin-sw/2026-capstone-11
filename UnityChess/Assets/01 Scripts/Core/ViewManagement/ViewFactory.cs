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
        [SerializeField]
        private ViewRegistry registry;
        [SerializeField]
        private ChessUIEventBus UIEventBus;
        [SerializeField]
        private CardUnitDB cardDB;

        [SerializeField]
        private GameObject UnitBasePrefab;
        [SerializeField]
        private GameObject CardBasePrefab;
        
        [SerializeField]
        private List<ViewSpriteEntry> SpriteEntries;

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
            Transform OppoHandParent,
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
            CreateHandViews(state, localPlayerId, handParent, true);
            CreateHandViews(state, opponentPlayerId, OppoHandParent, false);
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
                    pos: unit.position
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
                var spriteRenderer = (view as UnitView).gameObject.GetComponent<SpriteRenderer>();

                // 플레이어 자신의 유닛/카드인지 확인하고 해당하는 스프라이트를 설정
                spriteRenderer.sprite = isMyUnit ? SpriteDict[key][0] : SpriteDict[key][1];
            }
        }

        private void CreateHandViews(GameStateStore state, string playerId, Transform handParent, bool isMyCard)
        {
            var hand = state.GetHand(playerId);

            foreach (var uid in hand)
            {
                if (!state.TryGetUnit(uid, out var entity))
                    continue;

                var visualType = isMyCard ? VisualType.MyCard : VisualType.OpponentCard;

                var data = new CardViewData(
                    id: new ViewID(ViewType.Card, uid.id),
                    type: ViewType.Card,
                    visualType: visualType,
                    cardId: entity.cardId
                );

                var view = Create(data, handParent);
                var key = new PrefabKey { Type = data.Type, defId = data.cardId };

                var image = (view as CardView).gameObject.GetComponent<Image>();

                // 플레이어 자신의 유닛/카드인지 확인하고 해당하는 스프라이트를 설정
                image.sprite = isMyCard ? SpriteDict[key][0] : SpriteDict[key][1];
            }
        }

        void Awake()
        {
            Init();
        }
    }
}
