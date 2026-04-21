using UnityEngine;
using ui.view;
using System;
using System.Collections.Generic;
using events.ui;
using core.data;
using ui.view.board;
using ui.view.card;
using ui.view.unit;
using Core.StateManagement;

namespace core.UI
{
    [Serializable]
    public struct PrefabKey
    {
        public ViewType Type;
        public string defId;
    }

    /// <summary>
    /// 뷰 프리팹과 뷰 ID를 연결하는 엔트리 클래스
    /// </summary>
    [Serializable]
    public class ViewPrefabEntry
    {
        public PrefabKey key;
        public GameObject Prefab;
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
        private List<ViewPrefabEntry> prefabEntries;
        // TODO: 아트 작업 완료 이후 각 유닛/카드에 맞는 프리팹을 자동 연결할 수 있도록 개선
        private Dictionary<PrefabKey, GameObject> prefabs = new Dictionary<PrefabKey, GameObject>();

        // 게임 시작 시 프리팹 엔트리를 딕셔너리에 등록
        public void Init()
        {
            foreach (var entry in prefabEntries)
            {
                if (entry == null || entry.Prefab == null)
                    continue;
                
                prefabs[entry.key] = entry.Prefab;
            }
        }
        
        public IView Create(BaseViewData data, Transform parent)
        {
            if (registry.Contains(data.Id))
                throw new Exception($"{data.Id} 뷰가 이미 존재합니다.");

            var key = new PrefabKey { Type = data.Type, defId = data.cardId };

            var go = Instantiate(prefabs[key], parent);
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

            CreateBoardViews(state, boardParent, isLocalPlayerP1);
            CreateHandViews(state, localPlayerId, handParent);
        }

        private void CreateBoardViews(GameStateStore state, Transform boardParent, bool isLocalPlayerP1)
        {
            var units = state.GetPlacedUnits();

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

                var view = Create(data, boardParent);

                if (view is MonoBehaviour mb)
                {
                    var boardView = boardParent.GetComponent<BoardView>();
                    var cell = BoardView.BoardToCell(unit.position, isLocalPlayerP1);
                    var worldPos = boardView.tilemap.GetCellCenterWorld(cell);
                    mb.transform.position = worldPos;
                }
            }
        }

        private void CreateHandViews(GameStateStore state, string localPlayerId, Transform handParent)
        {
            var hand = state.GetHand(localPlayerId);

            foreach (var uid in hand)
            {
                if (!state.TryGetUnit(uid, out var entity))
                    continue;

                var visualType = entity.isPlaced ? VisualType.SpellCard : VisualType.UnitCard;

                var data = new CardViewData(
                    id: new ViewID(ViewType.Card, uid.id),
                    type: ViewType.Card,
                    visualType: visualType,
                    cardId: entity.cardId
                );

                Create(data, handParent);
            }
        }


        void Awake()
        {
            Init();
        }
    }
}
