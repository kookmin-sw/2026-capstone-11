using UnityEngine;
using ui.view;
using System;
using System.Collections.Generic;
using events;

namespace core.UI
{
    /// <summary>
    /// 뷰를 생성하고 파괴하는 팩토리 클래스
    /// </summary>  
    public class ViewFactory : MonoBehaviour
    {
        [SerializeField]
        private ViewRegistry registry;
        [SerializeField]
        private IEventBus UIEventBus;

        [SerializeField]
        private Dictionary<ViewType, GameObject> prefabs;

        public IView Create(BaseViewData data, Transform parent)
        {
            if (registry.Contains(data.Id))
                throw new Exception($"{data.Id} 뷰가 이미 존재합니다.");

            var go = Instantiate(prefabs[data.Type], parent);
            var view = go.GetComponent<IView>();

            view.Init(data, UIEventBus);
            registry.Register(view, data.Id);

            return view;
        }

        public void Destroy(ViewID id)
        {
            var view = registry.Get(id);
            registry.Unregister(id);
            Destroy(((MonoBehaviour)view).gameObject);
        }
    }
}
