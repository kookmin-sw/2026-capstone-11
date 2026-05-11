using System;
using UnityEngine;
using ui.view.effect;

namespace ui.view.unit
{
    /// <summary>
    /// 유닛 아웃라인 하이라이트 표시 책임을 가지는 클래스
    /// </summary>
    public class UnitOutliner : MonoBehaviour
    {
        [SerializeField] private SpriteRenderer spriteRenderer;
        [SerializeField] private Color[] outlineColors;

        Color GetColor(OutlineType state) => state switch
        {
            OutlineType.Targetable => outlineColors[0],
            OutlineType.Selectable => outlineColors[1],
            OutlineType.Selected => outlineColors[2],
            _ => Color.clear
        };

        private OutlineType state = OutlineType.None;

        public void Init(Sprite sprite)
        {
            spriteRenderer.sprite = sprite;
            SetHighlight(OutlineType.None);
        }

        public void SetHighlight(OutlineType type)
        {
            state = type;
            
            spriteRenderer.enabled = type != OutlineType.None;
            spriteRenderer.color = GetColor(type);
        }

        // TODO: 애니메이션 적용 시 스프라이트 동기화 코드 작성
        void LateUpdate()
        {
        
        }
    }
}