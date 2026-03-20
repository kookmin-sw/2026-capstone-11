using UnityEngine;

public class ProgramIsRunning : MonoBehaviour
{
    public Vector3 Rotate;

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        transform.Rotate(Rotate);
    }
}
