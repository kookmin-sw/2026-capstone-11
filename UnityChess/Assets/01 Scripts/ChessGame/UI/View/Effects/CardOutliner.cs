using System;
using UnityEngine;
using UnityEngine.UI;
using ui.view.effect;

namespace ui.view.card
{
    /// <summary>
    /// 유닛 아웃라인 하이라이트 표시 책임을 가지는 클래스
    /// </summary>
    public class CardOutliner : MonoBehaviour
    {
        [SerializeField] private Image image;
        [SerializeField] private Color outlineColor;

        Color GetColor(OutlineType state) => state switch
        {
            OutlineType.Selected => outlineColor,
            _ => Color.clear
        };

        private OutlineType state = OutlineType.None;

        public void Init(Sprite sprite)
        {
            image.sprite = sprite;
            SetHighlight(OutlineType.None);
        }

        public void SetHighlight(OutlineType type)
        {
            state = type;
            
            image.enabled = type != OutlineType.None;
            image.color = GetColor(type);
        }

        // TODO: 애니메이션 적용 시 스프라이트 동기화 코드 작성
        void LateUpdate()
        {
        
        }
    }
}